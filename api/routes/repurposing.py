"""
Repurposing route — return AI-ranked drug repurposing candidates for a result.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.result import Result
from models.submission import Submission
from models.patient import Patient
from routes.auth import get_current_patient
from services.trial_integration import fetch_trials_by_gene, fetch_trials_by_variant
from utils.http import not_found_error
from middleware.rate_limit import limiter, READ_LIMIT

router = APIRouter(prefix="/api/repurposing", tags=["repurposing"])


@router.get("/{result_id}")
@limiter.limit(READ_LIMIT)
async def get_repurposing_candidates(
    request: Request,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")

    # Verify this result belongs to the authenticated patient
    result = (await db.execute(
        select(Result)
        .join(Submission)
        .join(Patient)
        .where(
            Result.id == result_id,
            Patient.keycloak_id == keycloak_id,
        )
        .options(selectinload(Result.repurposing_candidates))
    )).scalar_one_or_none()

    if not result:
        raise not_found_error(request, "Result not found.")

    if not result.has_targetable_mutation:
        return {
            "result_id": result_id,
            "has_targetable_mutation": False,
            "message": "No targetable mutations were found for this sample.",
            "candidates": [],
        }

    candidates = sorted(
        result.repurposing_candidates,
        key=lambda c: c.rank_score or 0,
        reverse=True,
    )

    return {
        "result_id": result_id,
        "target_gene": result.target_gene,
        "has_targetable_mutation": True,
        "candidates": [
            {
                "drug_name": c.drug_name,
                "chembl_id": c.chembl_id,
                "approval_status": c.approval_status,
                "mechanism": c.mechanism,
                "binding_score": c.binding_score,
                "opentargets_score": c.opentargets_score,
                "rank_score": c.rank_score,
                "evidence_sources": c.evidence_sources or [],
                "matched_terms": c.matched_terms or [],
            }
            for c in candidates
        ],
    }


@router.get("/{result_id}/trials")
@limiter.limit(READ_LIMIT)
async def get_clinical_trial_matches(
    request: Request,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Layer 3: live ClinicalTrials.gov matching for the authenticated patient's result."""
    keycloak_id = token_payload.get("sub")

    result = (await db.execute(
        select(Result)
        .join(Submission)
        .join(Patient)
        .where(
            Result.id == result_id,
            Patient.keycloak_id == keycloak_id,
        )
    )).scalar_one_or_none()

    if not result:
        raise not_found_error(request, "Result not found.")

    submission = (await db.execute(
        select(Submission)
        .where(Submission.id == result.submission_id)
        .options(selectinload(Submission.mutations))
    )).scalar_one_or_none()

    if not submission:
        raise not_found_error(request, "Submission not found.")

    primary_gene = result.target_gene
    if not primary_gene and submission.mutations:
        primary_gene = submission.mutations[0].gene

    if not primary_gene:
        return {
            "result_id": result_id,
            "cancer_type": submission.cancer_type,
            "target_gene": None,
            "trials": [],
            "message": "No target gene available for trial matching.",
        }

    # Use variant-specific matching when the top mutation has an HGVS notation
    top_variant: str | None = None
    if submission.mutations:
        hgvs = submission.mutations[0].hgvs_notation or ""
        # Extract short form e.g. "T790M" from "p.Thr790Met" or pass through
        import re as _re
        _AA3 = {"Ala":"A","Arg":"R","Asn":"N","Asp":"D","Cys":"C","Gln":"Q","Glu":"E",
                "Gly":"G","His":"H","Ile":"I","Leu":"L","Lys":"K","Met":"M","Phe":"F",
                "Pro":"P","Ser":"S","Thr":"T","Trp":"W","Tyr":"Y","Val":"V","Ter":"*"}
        v = hgvs.lstrip("p.")
        m3 = _re.match(r"^([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|\*)$", v)
        if m3:
            ref = _AA3.get(m3.group(1)); alt = _AA3.get(m3.group(3), m3.group(3))
            if ref: top_variant = f"{ref}{m3.group(2)}{alt}"
        elif _re.match(r"^[A-Z\*]\d+[A-Z\*]$", v):
            top_variant = v

    if top_variant:
        trials = await fetch_trials_by_variant(
            gene=primary_gene,
            variant=top_variant,
            cancer_type=submission.cancer_type,
            limit=20,
        )
    else:
        trials = await fetch_trials_by_gene(
            gene=primary_gene,
            cancer_type=submission.cancer_type,
            limit=20,
        )
        for t in trials:
            t["relevance_score"] = 0.5

    filtered: list[dict] = []
    for t in trials:
        title = str(t.get("title") or "")
        status_text = str(t.get("status") or "")
        phase = str(t.get("phase") or "")
        filtered.append(
            {
                "trial_id": t.get("trial_id"),
                "title": title,
                "phase": phase,
                "status": status_text,
                "cancer_type": t.get("cancer_type"),
                "drugs": t.get("drugs") or [],
                "relevance_score": t.get("relevance_score", 0.5),
                "basket_trial": any(k in title.lower() for k in ("basket", "agnostic", "histology")),
                "expanded_access_hint": "expanded access" in title.lower() or "compassionate" in title.lower(),
                "trial_url": f"https://clinicaltrials.gov/study/{t.get('trial_id')}" if t.get("trial_id") else None,
                "source": "ClinicalTrials.gov",
            }
        )

    return {
        "result_id": result_id,
        "cancer_type": submission.cancer_type,
        "target_gene": primary_gene,
        "variant": top_variant,
        "trials": filtered[:20],
        "message": "Live variant-matched trial search from ClinicalTrials.gov." if top_variant
                   else "Live gene-level trial search from ClinicalTrials.gov.",
    }


# ── Immunotherapy biomarkers endpoint ─────────────────────────────────────────

@router.get("/{result_id}/immunotherapy")
@limiter.limit(READ_LIMIT)
async def get_immunotherapy_profile(
    request: Request,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return the immunotherapy biomarker profile (TMB, MSI-H, HRD, POLE) for a result."""
    keycloak_id = token_payload.get("sub")

    result = (await db.execute(
        select(Result)
        .join(Submission)
        .join(Patient)
        .where(Result.id == result_id, Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()

    if not result:
        raise not_found_error(request, "Result not found.")

    if not result.immunotherapy_profile:
        return {
            "result_id": result_id,
            "available": False,
            "message": "Immunotherapy profile not yet computed for this result.",
            "profile": None,
        }

    return {
        "result_id": result_id,
        "available": True,
        "profile": result.immunotherapy_profile,
    }


# ── Mutational signatures endpoint ────────────────────────────────────────────

@router.get("/{result_id}/signatures")
@limiter.limit(READ_LIMIT)
async def get_mutational_signature(
    request: Request,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return the dominant SBS mutational signature and treatment implication for a result."""
    keycloak_id = token_payload.get("sub")

    result = (await db.execute(
        select(Result)
        .join(Submission)
        .join(Patient)
        .where(Result.id == result_id, Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()

    if not result:
        raise not_found_error(request, "Result not found.")

    if not result.mutational_signature:
        return {
            "result_id": result_id,
            "available": False,
            "message": "Mutational signature analysis not available for this result.",
            "signature": None,
        }

    return {
        "result_id": result_id,
        "available": True,
        "signature": result.mutational_signature,
    }


# ── Combination therapy endpoint ──────────────────────────────────────────────

@router.get("/{result_id}/combinations")
@limiter.limit(READ_LIMIT)
async def get_combination_therapy(
    request: Request,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return combination therapy suggestions for a result."""
    keycloak_id = token_payload.get("sub")

    result = (await db.execute(
        select(Result)
        .join(Submission)
        .join(Patient)
        .where(Result.id == result_id, Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()

    if not result:
        raise not_found_error(request, "Result not found.")

    combinations = result.combination_therapy or []

    return {
        "result_id": result_id,
        "count": len(combinations),
        "combinations": combinations,
        "message": (
            f"{len(combinations)} evidence-based combination regimen(s) identified."
            if combinations else
            "No combination therapy suggestions available for this result."
        ),
    }
