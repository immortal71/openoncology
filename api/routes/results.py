"""
Results route — return mutation analysis report for a submission.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.submission import Submission
from models.patient import Patient
from models.result import Result
from routes.auth import get_current_patient
from schemas import ResultsResponse, SubmissionStatusOut
from services.intended_use import intended_use_payload
from utils.http import conflict_error, not_found_error
from middleware.rate_limit import limiter, READ_LIMIT

router = APIRouter(prefix="/api/results", tags=["results"])

logger = logging.getLogger(__name__)


@router.get("/{submission_id}", response_model=ResultsResponse)
@limiter.limit(READ_LIMIT)
async def get_results(
    request: Request,
    submission_id: str,
    include_oncologist_report: bool = Query(
        default=False,
        description=(
            "When true, include the full structured oncologist/tumor-board report "
            "in the response. Omitted by default to keep the patient-facing payload small."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")

    # Ensure the submission belongs to this patient
    submission = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(
            Submission.id == submission_id,
            Patient.keycloak_id == keycloak_id,
        )
        .options(
            selectinload(Submission.mutations),
            selectinload(Submission.result).selectinload(Result.repurposing_candidates),
        )
    )).scalar_one_or_none()

    if not submission:
        raise not_found_error(request, "Submission not found.")

    if submission.status.value not in ("complete",):
        return {
            "submission_id": submission_id,
            "status": submission.status,
            "message": "Analysis is still in progress. No local fallback result is generated in truth-only mode.",
        }

    result = submission.result
    mutations = submission.mutations

    # Which of the three end states this analysis reached. An empty candidate
    # list used to be indistinguishable from "we never looked", which became a
    # real possibility once the oncology-relevance gate started removing
    # non-cancer drugs from Tier 2. Callers need to tell the cases apart.
    has_target = bool(result and result.target_gene)
    has_candidates = bool(result and result.repurposing_candidates)
    if not mutations:
        recommendation_state = "no_mutations_detected"
    elif not has_target:
        recommendation_state = "no_targetable_mutation"
    elif not has_candidates:
        recommendation_state = "no_approved_therapy_found"
    else:
        recommendation_state = "candidates_available"

    custom_drug_possible = bool(has_target or mutations)
    custom_drug_reason = (
        # A confirmed target with nothing approved against it is exactly the
        # population custom discovery exists for, so say that rather than the
        # generic "we have a target".
        "no_approved_therapy_found" if recommendation_state == "no_approved_therapy_found" else
        "target_gene_available" if has_target else
        "mutation_profile_available" if mutations else
        "insufficient_genomic_signal"
    )

    # Build mutation summary list for report generators
    mutation_list = [
        {
            "gene": m.gene,
            "mutation_type": m.mutation_type,
            "hgvs_notation": m.hgvs_notation,
            "classification": str(m.classification.value) if m.classification else None,
            "oncokb_level": str(m.oncokb_level.value) if m.oncokb_level else None,
            "is_targetable": m.is_targetable,
            "alphamissense_score": m.alphamissense_score,
            # None means this variant's lookup state was never recorded, which
            # is not the same as a lookup that succeeded and found nothing (F3).
            "evidence_lookup_status": (
                m.evidence_lookup_status.value if m.evidence_lookup_status else None
            ),
        }
        for m in mutations
    ]

    # Sections that were requested but could not be built. Empty on the normal
    # path. A reader must be able to tell "this section has nothing to say" from
    # "this section could not be produced".
    generation_errors: list[str] = []

    # ── Patient-facing summary (template-only, always generated) ──────────
    patient_summary_sections: dict = {}
    patient_summary_text: str = ""
    try:
        from services.patient_summary import generate_patient_summary

        ranked = (result.ranked_candidates if result and hasattr(result, "ranked_candidates") else None) or []
        gene = result.target_gene if result else None
        ps = generate_patient_summary(
            ranked_candidates=ranked,
            mutation_summary=mutation_list,
            cancer_type=submission.cancer_type,
            gene=gene,
        )
        patient_summary_sections = ps.sections
        patient_summary_text = ps.plain_text
    except Exception:
        # Still never fails the response, but no longer disappears. A bare
        # `pass` here returned 200 with patient_summary: null, which reads
        # identically to "we generated a summary and it was empty". That is
        # hazard H3, a failure presented as a negative result, inside the
        # response the patient actually reads.
        logger.exception(
            "[results] patient summary generation failed for submission %s",
            submission_id,
        )
        generation_errors.append("patient_summary")

    # ── Oncologist report (generated on demand via query param) ────────────
    oncologist_report_data: dict = {}
    if include_oncologist_report:
        try:
            from services.oncologist_report import generate_oncologist_report

            ranked = (result.ranked_candidates if result and hasattr(result, "ranked_candidates") else None) or []
            onc_report = generate_oncologist_report(
                ranked_candidates=ranked,
                mutation_summary=mutation_list,
                cancer_type=submission.cancer_type,
                qc_report=submission.sample_qc,
                patient_id=str(submission.id),
            )
            oncologist_report_data = onc_report.sections
            oncologist_report_data["plain_text"] = onc_report.plain_text
        except Exception:
            # As above. A clinician who asked for the report and received
            # oncologist_report: null could not tell an empty report from a
            # crashed one.
            logger.exception(
                "[results] oncologist report generation failed for submission %s",
                submission_id,
            )
            generation_errors.append("oncologist_report")

    from services.sample_qc import qc_payload_for_api

    return {
        "submission_id": submission_id,
        "cancer_type": submission.cancer_type,
        "status": "complete",
        # Unconditional, and deliberately not inside patient_summary. The only
        # disclaimer this payload used to carry was nested in that section,
        # which is generated inside a try and becomes None when it fails. A
        # caller reading plain_language_summary after that failure got drug
        # names, has_targetable_mutation and per-mutation OncoKB levels with
        # nothing in the response saying what produced them.
        "intended_use": intended_use_payload(
            clinician_reviewed=bool(result.oncologist_reviewed) if result else False
        ),
        # The QC verdict stopped at the rendered report until now, so no API
        # consumer could tell a clean sample from a flagged one.
        "sample_qc": qc_payload_for_api(submission.sample_qc),
        # Stamped when the result was produced, not read now — the evidence table
        # can be refreshed in between. Absent means "not recorded", never "current".
        "evidence_provenance": (
            (result.evidence_provenance if result else None)
            or {"path": "not_recorded", "is_current": False,
                "caveat": "This result predates evidence provenance capture; "
                          "the age and source of the evidence behind it are unknown."}
        ),
        "has_targetable_mutation": result.has_targetable_mutation if result else False,
        "target_gene": result.target_gene if result else None,
        "summary": result.summary_text if result else None,
        # patient_summary replaces plain_language_summary as the primary patient output
        "patient_summary": patient_summary_sections or None,
        "patient_summary_text": patient_summary_text or None,
        # kept for backward compatibility — populated from legacy result field
        "plain_language_summary": result.plain_language_summary if result else None,
        "cbioportal_data": result.cbioportal_data if result else None,
        "cosmic_sample_count": result.cosmic_sample_count if result else None,
        "oncologist_reviewed": result.oncologist_reviewed if result else False,
        "oncologist_notes": result.oncologist_notes if result else None,
        "custom_drug_possible": custom_drug_possible,
        "custom_drug_reason": custom_drug_reason,
        # Empty on the normal path. Names any section that was requested and
        # could not be generated, so a null section is not read as an empty one.
        "algorithm_version": (result.algorithm_version if result else None),
        "generation_errors": generation_errors,
        # oncologist_report: only populated when include_oncologist_report=true
        "oncologist_report": oncologist_report_data or None,
        "mutations": [
            {
                "gene": m.gene,
                "mutation_type": m.mutation_type,
                "hgvs": m.hgvs_notation,
                "classification": str(m.classification.value) if m.classification else None,
                "oncokb_level": str(m.oncokb_level.value) if m.oncokb_level else None,
                "is_targetable": m.is_targetable,
                "alphamissense_score": m.alphamissense_score,
                "evidence_lookup_status": (
                    m.evidence_lookup_status.value if m.evidence_lookup_status else None
                ),
            }
            for m in mutations
        ],
        "result_id": result.id if result else None,
        "immunotherapy_profile": result.immunotherapy_profile if result else None,
        "mutational_signature": result.mutational_signature if result else None,
        "combination_therapy": result.combination_therapy or [] if result else [],
        "recommendation_state": recommendation_state,
        "excluded_candidates": (result.excluded_candidates or []) if result else [],
    }


@router.get("/dashboard/all", response_model=list[SubmissionStatusOut])
@limiter.limit(READ_LIMIT)
async def get_all_submissions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return all submissions for the authenticated patient's dashboard."""
    keycloak_id = token_payload.get("sub")
    submissions = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(Patient.keycloak_id == keycloak_id)
        .order_by(Submission.submitted_at.desc())
    )).scalars().all()

    return [
        {
            "submission_id": s.id,
            "cancer_type": s.cancer_type,
            "status": s.status,
            "submitted_at": s.submitted_at,
            "completed_at": s.completed_at,
        }
        for s in submissions
    ]


# ---------------------------------------------------------------------------
# PDF export endpoints
# ---------------------------------------------------------------------------

async def _get_verified_submission(
    request: Request,
    submission_id: str,
    db: AsyncSession,
    token_payload: dict,
):
    """Shared helper: fetch submission + verify ownership, 404/403 on failure."""
    keycloak_id = token_payload.get("sub")
    submission = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(
            Submission.id == submission_id,
            Patient.keycloak_id == keycloak_id,
        )
        .options(
            selectinload(Submission.mutations),
            selectinload(Submission.result),
        )
    )).scalar_one_or_none()
    if not submission:
        raise not_found_error(request, "Submission not found.")
    if submission.status.value != "complete":
        raise conflict_error(request, "Analysis not yet complete.")
    return submission


@router.get(
    "/{submission_id}/patient-letter.pdf",
    summary="Download patient summary letter as PDF",
    description=(
        "Generates and returns the patient-facing summary letter as a PDF file. "
        "If WeasyPrint is not installed the response is HTML with Content-Type text/html."
    ),
    response_class=Response,
)
@limiter.limit(READ_LIMIT)
async def download_patient_letter_pdf(
    request: Request,
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    from services.patient_summary import generate_patient_summary
    from services.pdf_export import generate_patient_letter_document

    submission = await _get_verified_submission(request, submission_id, db, token_payload)
    result = submission.result
    mutations = submission.mutations
    mutation_list = [
        {
            "gene": m.gene,
            "mutation_type": m.mutation_type,
            "hgvs_notation": m.hgvs_notation,
            "classification": str(m.classification.value) if m.classification else None,
            "oncokb_level": str(m.oncokb_level.value) if m.oncokb_level else None,
            "is_targetable": m.is_targetable,
            "alphamissense_score": m.alphamissense_score,
            # None means this variant's lookup state was never recorded, which
            # is not the same as a lookup that succeeded and found nothing (F3).
            "evidence_lookup_status": (
                m.evidence_lookup_status.value if m.evidence_lookup_status else None
            ),
        }
        for m in mutations
    ]
    ranked = (result.ranked_candidates if result and hasattr(result, "ranked_candidates") else None) or []
    ps = generate_patient_summary(
        ranked_candidates=ranked,
        mutation_summary=mutation_list,
        cancer_type=submission.cancer_type,
        gene=result.target_gene if result else None,
    )
    pdf_bytes, media_type, ext = generate_patient_letter_document(ps.sections)
    filename = f"patient_letter_{submission_id}{ext}"
    return Response(
        content=pdf_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{submission_id}/oncologist-report.pdf",
    summary="Download full oncologist report as PDF",
    description=(
        "Generates and returns the full structured oncologist / tumour board report as a PDF. "
        "If WeasyPrint is not installed the response is HTML with Content-Type text/html."
    ),
    response_class=Response,
)
@limiter.limit(READ_LIMIT)
async def download_oncologist_report_pdf(
    request: Request,
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    from services.oncologist_report import generate_oncologist_report
    from services.pdf_export import generate_oncologist_report_document

    submission = await _get_verified_submission(request, submission_id, db, token_payload)
    result = submission.result
    mutations = submission.mutations
    mutation_list = [
        {
            "gene": m.gene,
            "mutation_type": m.mutation_type,
            "hgvs_notation": m.hgvs_notation,
            "classification": str(m.classification.value) if m.classification else None,
            "oncokb_level": str(m.oncokb_level.value) if m.oncokb_level else None,
            "is_targetable": m.is_targetable,
            "alphamissense_score": m.alphamissense_score,
            # None means this variant's lookup state was never recorded, which
            # is not the same as a lookup that succeeded and found nothing (F3).
            "evidence_lookup_status": (
                m.evidence_lookup_status.value if m.evidence_lookup_status else None
            ),
        }
        for m in mutations
    ]
    ranked = (result.ranked_candidates if result and hasattr(result, "ranked_candidates") else None) or []
    onc_report = generate_oncologist_report(
        ranked_candidates=ranked,
        mutation_summary=mutation_list,
        cancer_type=submission.cancer_type,
        qc_report=submission.sample_qc,
        patient_id=str(submission.id),
    )
    pdf_bytes, media_type, ext = generate_oncologist_report_document(onc_report)
    filename = f"oncologist_report_{submission_id}{ext}"
    return Response(
        content=pdf_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
