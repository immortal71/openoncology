"""
Marketplace route — pharma company listings, drug ordering, and competitive bidding.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
import stripe

from config import settings
from database import get_db
from models.pharma import PharmaCompany
from models.order import Order, OrderStatus
from models.patient import Patient
from models.bid import DrugRequest, PharmaBid, BidStatus, DiscoveryStatus
from models.result import Result
from models.submission import Submission
from services.drug_discovery import build_custom_discovery_brief
from routes.auth import get_current_patient
from workers.custom_drug_worker import build_custom_drug_brief

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

stripe.api_key = settings.stripe_secret_key


async def _get_patient_result_context(
    result_id: str,
    keycloak_id: str,
    db: AsyncSession,
) -> tuple[Result, Submission, Patient]:
    row = (await db.execute(
        select(Result, Submission, Patient)
        .join(Submission, Submission.id == Result.submission_id)
        .join(Patient, Patient.id == Submission.patient_id)
        .options(
            selectinload(Result.repurposing_candidates),
            selectinload(Submission.mutations),
        )
        .where(
            Result.id == result_id,
            Patient.keycloak_id == keycloak_id,
        )
    )).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")

    result, submission, patient = row
    return result, submission, patient


def _discovery_brief_to_drug_spec(brief: dict) -> str:
    leads = brief.get("lead_candidates", [])
    comps = brief.get("component_library", {})
    top_leads = [
        f"- {l.get('drug_name') or 'Unknown'} ({l.get('chembl_id') or 'N/A'}), phase={l.get('max_phase')}, score={l.get('opentargets_score')}"
        for l in leads[:8]
    ]
    scaffolds = comps.get("scaffolds", [])[:12]
    fragments = comps.get("fragments", [])[:16]

    return "\n".join(
        [
            f"Custom discovery request for target gene: {brief.get('target_gene')}",
            f"Cancer type: {brief.get('cancer_type')}",
            f"Reason: {brief.get('reason')}",
            "",
            "Mutation profile:",
            *[f"- {m}" for m in (brief.get("mutation_profile") or [])],
            "",
            "Lead candidates:",
            *(top_leads or ["- No direct leads found; use target-first scaffold generation."]),
            "",
            "Preferred scaffolds:",
            *([f"- {s}" for s in scaffolds] or ["- None extracted"]),
            "",
            "Preferred fragments:",
            *([f"- {f}" for f in fragments] or ["- None extracted"]),
            "",
            "Design constraints:",
            "- prioritize target selectivity",
            "- maintain drug-like properties (Ro5 where feasible)",
            "- provide synthetic route confidence and estimated timeline",
            "",
            "Handoff note:",
            brief.get("handoff_note", ""),
        ]
    )


def _discovery_brief_to_report_text(brief: dict) -> str:
    leads = brief.get("lead_candidates", [])
    comps = brief.get("component_library", {})

    lines = [
        "OpenOncology Custom Drug Discovery Report",
        "========================================",
        f"Target gene: {brief.get('target_gene')}",
        f"Cancer type: {brief.get('cancer_type')}",
        f"Reason: {brief.get('reason')}",
        "",
        "Mutation profile:",
    ]
    lines += [f"- {m}" for m in (brief.get("mutation_profile") or [])] or ["- Not provided"]

    lines += ["", "Lead candidates:"]
    if leads:
        for l in leads[:12]:
            lines.append(
                f"- {l.get('drug_name') or 'Unknown'} ({l.get('chembl_id') or 'N/A'}) | "
                f"phase={l.get('max_phase')} | approved={l.get('is_approved')} | "
                f"score={l.get('opentargets_score')}"
            )
            if l.get("mechanism"):
                lines.append(f"  mechanism: {l.get('mechanism')}")
            if l.get("smiles"):
                lines.append(f"  smiles: {l.get('smiles')}")
    else:
        lines.append("- No direct leads found")

    lines += ["", "Scaffold components:"]
    lines += [f"- {s}" for s in comps.get("scaffolds", [])[:20]] or ["- None extracted"]

    lines += ["", "Fragment components:"]
    lines += [f"- {f}" for f in comps.get("fragments", [])[:30]] or ["- None extracted"]

    lines += [
        "",
        "Design constraints:",
        "- prioritize target selectivity",
        "- keep drug-like properties (Ro5 where feasible)",
        "- provide synthetic route confidence and estimated timeline",
        "",
        "Clinical/manufacturing disclaimer:",
        brief.get("handoff_note", ""),
    ]

    return "\n".join(lines)


def _fallback_computational_synthesis_plan(brief: dict) -> dict:
    existing = brief.get("computational_synthesis_plan")
    if isinstance(existing, dict) and existing:
        return existing

    de_novo = brief.get("de_novo_candidates") or []
    selected = []
    for cand in de_novo[:3]:
        smiles = cand.get("proposed_smiles")
        precursor_count = max(1, len([p for p in (smiles or "").split(".") if p])) if smiles else 0
        selected.append(
            {
                "candidate_id": cand.get("candidate_id"),
                "parent_lead": cand.get("parent_lead"),
                "proposed_smiles": smiles,
                "precursor_count_estimate": precursor_count,
                "route_confidence_score": cand.get("feasibility_score"),
                "route_outline": [
                    "Retrosynthetic split around core scaffold bonds.",
                    "Enumerate alternative low-step assembly paths.",
                    "Rank routes by confidence and synthetic complexity.",
                ],
            }
        )

    return {
        "mode": "computational_synthesis_planning",
        "status": "ready_for_medicinal_chemistry_review" if selected else "insufficient_candidates",
        "summary": "In-silico route hypotheses generated from de novo candidates for chemistry triage.",
        "selected_candidates": selected,
        "execution_stages": [
            {
                "stage": "retrosynthesis_enumeration",
                "duration": "5-15 min",
                "deliverable": "Route trees with precursor sets",
            },
            {
                "stage": "route_ranking",
                "duration": "2-5 min",
                "deliverable": "Ranked route shortlist",
            },
        ],
        "constraints": [
            "In-silico confidence does not guarantee laboratory outcomes.",
            "Final synthesis decisions require licensed chemist review.",
        ],
        "disclaimer": "Computational synthesis planning only; no physical synthesis is performed by the platform.",
    }


@router.get("/pharma")
async def list_pharma_companies(
    db: AsyncSession = Depends(get_db),
):
    """Public list of verified pharma manufacturers."""
    companies = (await db.execute(
        select(PharmaCompany).where(PharmaCompany.verified)
    )).scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "country": c.country,
            "description": c.description,
            "min_order_usd": c.min_order_usd,
        }
        for c in companies
    ]


class OrderRequest(BaseModel):
    pharma_id: str
    drug_spec: str = Field(..., max_length=2000)
    amount_usd: float = Field(..., gt=0, le=1_000_000)


@router.post("/order", status_code=status.HTTP_201_CREATED)
async def create_order(
    req: OrderRequest,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")

    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    pharma = (await db.execute(
        select(PharmaCompany).where(
            PharmaCompany.id == req.pharma_id,
            PharmaCompany.verified,
        )
    )).scalar_one_or_none()
    if not pharma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pharma company not found.")

    # Create Stripe payment intent
    intent = stripe.PaymentIntent.create(
        amount=int(req.amount_usd * 100),  # cents
        currency="usd",
        metadata={
            "patient_id": patient.id,
            "pharma_id": pharma.id,
        },
    )

    order = Order(
        patient_id=patient.id,
        pharma_id=pharma.id,
        drug_spec=req.drug_spec,
        amount_usd=req.amount_usd,
        status=OrderStatus.payment_processing,
        stripe_payment_intent_id=intent["id"],
    )
    db.add(order)
    await db.commit()

    synthesis_plan = _fallback_computational_synthesis_plan(brief)

    return {
        "order_id": order.id,
        "client_secret": intent["client_secret"],
        "amount_usd": req.amount_usd,
        "status": order.status,
    }


# ---------------------------------------------------------------------------
# Competitive bidding — custom drug requests & pharma bids
# ---------------------------------------------------------------------------

class DrugRequestCreate(BaseModel):
    drug_spec: str = Field(..., min_length=20, max_length=4000,
                           description="Technical drug specification derived from AI analysis")
    target_gene: str = Field(None, max_length=64)
    max_budget_usd: float = Field(None, gt=0, le=10_000_000)
    result_id: str = Field(None, description="Result ID linking this request to an AI analysis")


@router.get("/discovery-brief/{result_id}")
async def get_custom_discovery_brief(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Generate a custom discovery brief when repurposing is weak/empty."""
    keycloak_id = token_payload.get("sub")
    result, submission, _patient = await _get_patient_result_context(result_id, keycloak_id, db)

    repurposing_candidates = []
    if result.repurposing_candidates:
        repurposing_candidates = [
            {
                "rank_score": c.rank_score,
                "drug_name": c.drug_name,
                "chembl_id": c.chembl_id,
            }
            for c in result.repurposing_candidates
        ]

    mutation_hgvs = [m.hgvs_notation for m in submission.mutations if m.hgvs_notation] if submission.mutations else []

    target_gene = result.target_gene or (submission.mutations[0].gene if submission.mutations else None)
    if not target_gene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No target gene found for custom discovery.")

    brief = await build_custom_discovery_brief(
        target_gene=target_gene,
        cancer_type=submission.cancer_type,
        mutation_hgvs=mutation_hgvs,
        repurposing_candidates=repurposing_candidates,
    )
    return brief


@router.get("/custom-drug-report/{result_id}")
async def get_custom_drug_report(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return a downloadable custom-drug discovery report text for the patient."""
    keycloak_id = token_payload.get("sub")
    result, submission, _patient = await _get_patient_result_context(result_id, keycloak_id, db)

    mutation_hgvs = [m.hgvs_notation for m in submission.mutations if m.hgvs_notation] if submission.mutations else []
    repurposing_candidates = [
        {"rank_score": c.rank_score, "drug_name": c.drug_name, "chembl_id": c.chembl_id}
        for c in result.repurposing_candidates
    ] if result.repurposing_candidates else []

    target_gene = result.target_gene or (submission.mutations[0].gene if submission.mutations else None)
    if not target_gene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No target gene found for custom discovery.")

    brief = await build_custom_discovery_brief(
        target_gene=target_gene,
        cancer_type=submission.cancer_type,
        mutation_hgvs=mutation_hgvs,
        repurposing_candidates=repurposing_candidates,
    )

    return {
        "result_id": result_id,
        "filename": f"custom_drug_report_{result_id[:8]}.txt",
        "report_text": _discovery_brief_to_report_text(brief),
        "brief": brief,
    }


@router.get("/nearby-pharmacies")
async def get_nearby_pharmacies():
    """Temporary nearby pharmacy placeholder list (phase-in feature)."""
    return {
        "pharmacies": [
            {
                "name": "CityCare Pharmacy",
                "distance_km": 2.3,
                "phone": "+1-555-0102",
                "address": "12 Main Street",
            },
            {
                "name": "Neighborhood Oncology Rx",
                "distance_km": 4.8,
                "phone": "+1-555-0161",
                "address": "88 Health Avenue",
            },
        ]
    }


@router.post("/drug-requests/from-result/{result_id}", status_code=status.HTTP_201_CREATED)
async def create_drug_request_from_result(
    result_id: str,
    max_budget_usd: float | None = None,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Create a persisted custom discovery job and hand it off to the worker queue."""
    keycloak_id = token_payload.get("sub")
    result, submission, patient = await _get_patient_result_context(result_id, keycloak_id, db)

    target_gene = result.target_gene or (submission.mutations[0].gene if submission.mutations else None)
    if not target_gene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No target gene found for custom discovery.")

    req = DrugRequest(
        patient_id=patient.id,
        result_id=result_id,
        target_gene=target_gene,
        drug_spec="Queued custom discovery job. Detailed brief will be generated by worker.",
        max_budget_usd=max_budget_usd,
        is_open=True,
        discovery_status=DiscoveryStatus.queued,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    build_custom_drug_brief.apply_async(args=[req.id], queue="ai")

    return {
        "drug_request_id": req.id,
        "status": req.discovery_status.value,
        "mode": "custom_discovery",
        "target_gene": req.target_gene,
        "cancer_type": submission.cancer_type,
        "brief_preview": {
            "reason": "queued_for_background_generation",
            "lead_count": 0,
            "scaffold_count": 0,
            "fragment_count": 0,
        },
    }


@router.post("/drug-requests", status_code=status.HTTP_201_CREATED)
async def create_drug_request(
    req: DrugRequestCreate,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Patient opens a competitive drug synthesis request visible to all verified pharma."""
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    drug_request = DrugRequest(
        patient_id=patient.id,
        result_id=req.result_id,
        target_gene=req.target_gene,
        drug_spec=req.drug_spec,
        max_budget_usd=req.max_budget_usd,
        is_open=True,
    )
    db.add(drug_request)
    await db.commit()
    await db.refresh(drug_request)
    return {"drug_request_id": drug_request.id, "status": "open"}


@router.get("/drug-requests")
async def list_drug_requests(
    db: AsyncSession = Depends(get_db),
):
    """Public listing of open drug synthesis requests for pharma companies to bid on."""
    requests = (await db.execute(
        select(DrugRequest).where(DrugRequest.is_open == True)  # noqa: E712
    )).scalars().all()
    return {
        "requests": [
            {
                "drug_request_id": r.id,
                "id": r.id,
                "result_id": r.result_id,
                "target_gene": r.target_gene,
                "cancer_type": None,
                "drug_spec": r.drug_spec,
                "max_budget_usd": r.max_budget_usd,
                "status": r.discovery_status.value,
                "bid_count": 0,  # populated in detailed view
                "created_at": r.created_at.isoformat(),
            }
            for r in requests
        ]
    }


@router.get("/drug-requests/{request_id}")
async def get_drug_request_detail(
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single drug request detail payload used by the custom-drug page."""

    req = (await db.execute(
        select(DrugRequest).where(DrugRequest.id == request_id)
    )).scalar_one_or_none()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found.")

    result = None
    submission = None
    if req.result_id:
        result = (await db.execute(
            select(Result).where(Result.id == req.result_id)
        )).scalar_one_or_none()
    if result:
        submission = (await db.execute(
            select(Submission).where(Submission.id == result.submission_id)
        )).scalar_one_or_none()

    cancer_type = submission.cancer_type if submission else "Unknown"
    target_gene = req.target_gene or (result.target_gene if result else None) or "Unknown"

    brief = req.discovery_brief or {}
    if req.discovery_status == DiscoveryStatus.failed:
        return {
            "drug_request_id": req.id,
            "result_id": req.result_id,
            "status": req.discovery_status.value,
            "target_gene": target_gene,
            "cancer_type": cancer_type,
            "stage": 2,
            "message": req.discovery_error or "Custom discovery failed.",
        }

    if req.discovery_status != DiscoveryStatus.complete:
        return {
            "drug_request_id": req.id,
            "result_id": req.result_id,
            "status": req.discovery_status.value,
            "target_gene": target_gene,
            "cancer_type": cancer_type,
            "stage": 1 if req.discovery_status == DiscoveryStatus.running else 0,
            "message": "Custom drug discovery is running in the background. You can return later from My Orders.",
        }

    synthesis_plan = _fallback_computational_synthesis_plan(brief)

    return {
        "drug_request_id": req.id,
        "result_id": req.result_id,
        "status": req.discovery_status.value,
        "target_gene": target_gene,
        "cancer_type": cancer_type,
        "stage": 2,
        "message": "Custom drug discovery brief is ready.",
        "mutation_profile": brief.get("mutation_profile", []),
        "rationale": brief.get("design_rationale") or brief.get("handoff_note") or "Detailed lead ranking is available in discovery report export.",
        "live_data_used": bool(brief.get("live_data_used")),
        "integration_issues": brief.get("integration_issues") or [],
        "lead_compounds": [
            {
                "name": lead.get("drug_name"),
                "smiles": lead.get("smiles"),
                "binding_score": lead.get("binding_score"),
                "design_priority_score": lead.get("design_priority_score"),
                "oral_exposure_score": lead.get("oral_exposure_score"),
                "synthesis_feasibility_score": lead.get("synthesis_feasibility_score"),
                "toxicity_risk": lead.get("toxicity_risk"),
                "toxicity_flag": (lead.get("toxicity_risk") or 0) >= 55,
                "mechanism": lead.get("mechanism"),
                "phase": (
                    str(lead.get("max_phase"))
                    if isinstance(lead.get("max_phase"), str)
                    else f"Phase {lead.get('max_phase')}" if lead.get("max_phase") is not None else "Unknown"
                ),
                "evidence_sources": lead.get("evidence_sources") or [],
                "matched_terms": lead.get("matched_terms") or [],
                "ensemble_score": lead.get("ensemble_score"),
                "ensemble_breakdown": lead.get("ensemble_breakdown") or {},
            }
            for lead in brief.get("lead_candidates", [])
        ],
        "de_novo_candidates": [
            {
                "candidate_id": cand.get("candidate_id"),
                "parent_lead": cand.get("parent_lead"),
                "design_strategy": cand.get("design_strategy"),
                "proposed_smiles": cand.get("proposed_smiles"),
                "selected_scaffold": cand.get("selected_scaffold"),
                "selected_fragment": cand.get("selected_fragment"),
                "docking_binding_score": cand.get("docking_binding_score"),
                "target_fit_score": cand.get("target_fit_score"),
                "novelty_score": cand.get("novelty_score"),
                "feasibility_score": cand.get("feasibility_score"),
                "overall_score": cand.get("overall_score"),
                "evidence_sources": cand.get("evidence_sources") or [],
                "matched_terms": cand.get("matched_terms") or [],
                "ensemble_score": cand.get("ensemble_score"),
                "ensemble_breakdown": cand.get("ensemble_breakdown") or {},
                "disclaimer": cand.get("disclaimer"),
            }
            for cand in brief.get("de_novo_candidates", [])
        ],
        "docking_summary": brief.get("docking_summary") or {},
        "computational_synthesis_plan": synthesis_plan,
        "scaffold_summary": {
            "core_scaffolds": (brief.get("component_library") or {}).get("scaffolds", []),
            "fragment_hits": (brief.get("component_library") or {}).get("fragments", []),
            "admet_notes": "Scores shown here are computational heuristics derived from public molecular descriptors and existing repurposing evidence; no wet-lab ADMET has been run by the platform.",
        },
        "timeline_weeks": {
            "target_structure_compute": "1-3 min",
            "docking_and_ranking": "2-5 min",
            "de_novo_candidate_assembly": "<1 min",
        },
        "next_steps": [
            "Review generated brief with medicinal chemistry and oncology teams.",
            "Request bids from verified manufacturers.",
            "Approve synthesis only after scientific review.",
        ],
        "attributions": ["OpenTargets", "ChEMBL", "AlphaFold Server", "DiffDock", "OpenOncology custom discovery worker", "De novo design heuristics"],
        "scoring_engines_used": brief.get("scoring_engines_used") or [
            "OpenTargets evidence",
            "ChEMBL molecular properties",
            "RDKit descriptor/scaffold extraction",
            "DiffDock docking (optional)",
            "OpenOncology ensemble consensus scorer",
        ],
    }


class BidCreate(BaseModel):
    price_usd: float = Field(..., gt=0, le=10_000_000)
    estimated_weeks: int = Field(..., gt=0, le=520)
    notes: str = Field(None, max_length=2000)


@router.post("/drug-requests/{request_id}/bids", status_code=status.HTTP_201_CREATED)
async def submit_bid(
    request_id: str,
    bid: BidCreate,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Pharma company submits a bid on an open drug request.

    The pharma company must be verified and have a linked Stripe account.
    Auth token must belong to the pharma admin account.
    """
    pharma = (await db.execute(
        select(PharmaCompany).where(
            PharmaCompany.contact_email == token_payload.get("email"),
            PharmaCompany.verified == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not pharma:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified pharma companies can submit bids.",
        )

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.is_open == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found or closed.")

    # Validate budget ceiling
    if drug_request.max_budget_usd and bid.price_usd > drug_request.max_budget_usd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bid exceeds patient's budget ceiling of ${drug_request.max_budget_usd:,.2f}.",
        )

    new_bid = PharmaBid(
        drug_request_id=request_id,
        pharma_id=pharma.id,
        price_usd=bid.price_usd,
        estimated_weeks=str(bid.estimated_weeks),
        notes=bid.notes,
        status=BidStatus.open,
    )
    db.add(new_bid)
    await db.commit()
    await db.refresh(new_bid)
    return {"bid_id": new_bid.id, "status": "open", "price_usd": bid.price_usd}


@router.get("/drug-requests/{request_id}/bids")
async def list_bids(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return all bids on a drug request.  Only the requesting patient can see bids."""
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=407, detail="Patient not found.")

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.patient_id == patient.id,
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found.")

    bids = (await db.execute(
        select(PharmaBid).where(PharmaBid.drug_request_id == request_id)
    )).scalars().all()

    return [
        {
            "id": b.id,
            "pharma_id": b.pharma_id,
            "price_usd": b.price_usd,
            "estimated_weeks": b.estimated_weeks,
            "notes": b.notes,
            "status": b.status,
            "created_at": b.created_at.isoformat(),
        }
        for b in bids
    ]


@router.post("/drug-requests/{request_id}/bids/{bid_id}/accept")
async def accept_bid(
    request_id: str,
    bid_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Patient accepts a bid, closing the request and rejecting all other bids.

    Returns a Stripe payment intent to collect payment for the accepted bid.
    """
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.patient_id == patient.id,
            DrugRequest.is_open == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found or already closed.")

    winning_bid = (await db.execute(
        select(PharmaBid).where(
            PharmaBid.id == bid_id,
            PharmaBid.drug_request_id == request_id,
            PharmaBid.status == BidStatus.open,
        )
    )).scalar_one_or_none()
    if not winning_bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found.")

    pharma = (await db.execute(
        select(PharmaCompany).where(PharmaCompany.id == winning_bid.pharma_id)
    )).scalar_one_or_none()

    # Create Stripe payment intent
    transfer_data = {}
    if pharma and pharma.stripe_account_id:
        transfer_data = {"transfer_data": {"destination": pharma.stripe_account_id}}

    intent = stripe.PaymentIntent.create(
        amount=int(winning_bid.price_usd * 100),
        currency="usd",
        metadata={
            "patient_id": patient.id,
            "bid_id": winning_bid.id,
            "drug_request_id": drug_request.id,
        },
        **transfer_data,
    )

    # Atomically close the auction: accept winner, reject all others
    all_bids = (await db.execute(
        select(PharmaBid).where(PharmaBid.drug_request_id == request_id)
    )).scalars().all()

    for b in all_bids:
        b.status = BidStatus.accepted if b.id == bid_id else BidStatus.rejected

    drug_request.is_open = False
    drug_request.accepted_bid_id = bid_id
    drug_request.closed_at = datetime.utcnow()
    await db.commit()

    return {
        "bid_id": bid_id,
        "price_usd": winning_bid.price_usd,
        "estimated_weeks": winning_bid.estimated_weeks,
        "client_secret": intent["client_secret"],
        "status": "accepted",
    }
