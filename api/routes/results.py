"""
Results route — return mutation analysis report for a submission.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.submission import Submission
from models.patient import Patient
from routes.auth import get_current_patient
from schemas import ResultsResponse, SubmissionStatusOut

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{submission_id}", response_model=ResultsResponse)
async def get_results(
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
            selectinload(Submission.result),
        )
    )).scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    if submission.status.value not in ("complete",):
        return {
            "submission_id": submission_id,
            "status": submission.status,
            "message": "Analysis is still in progress. No local fallback result is generated in truth-only mode.",
        }

    result = submission.result
    mutations = submission.mutations
    custom_drug_possible = bool((result and result.target_gene) or mutations)
    custom_drug_reason = (
        "target_gene_available" if (result and result.target_gene) else
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
        }
        for m in mutations
    ]

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
        pass  # never fail the response due to summary generation

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
                patient_id=str(submission.id),
            )
            oncologist_report_data = onc_report.sections
            oncologist_report_data["plain_text"] = onc_report.plain_text
        except Exception:
            pass  # never fail the response due to report generation

    return {
        "submission_id": submission_id,
        "cancer_type": submission.cancer_type,
        "status": "complete",
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
            }
            for m in mutations
        ],
        "result_id": result.id if result else None,
    }


@router.get("/dashboard/all", response_model=list[SubmissionStatusOut])
async def get_all_submissions(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    if submission.status.value != "complete":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analysis not yet complete.")
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
async def download_patient_letter_pdf(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    from services.patient_summary import generate_patient_summary
    from services.pdf_export import generate_patient_letter_document

    submission = await _get_verified_submission(submission_id, db, token_payload)
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
async def download_oncologist_report_pdf(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    from services.oncologist_report import generate_oncologist_report
    from services.pdf_export import generate_oncologist_report_document

    submission = await _get_verified_submission(submission_id, db, token_payload)
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
        }
        for m in mutations
    ]
    ranked = (result.ranked_candidates if result and hasattr(result, "ranked_candidates") else None) or []
    onc_report = generate_oncologist_report(
        ranked_candidates=ranked,
        mutation_summary=mutation_list,
        cancer_type=submission.cancer_type,
        patient_id=str(submission.id),
    )
    pdf_bytes, media_type, ext = generate_oncologist_report_document(onc_report)
    filename = f"oncologist_report_{submission_id}{ext}"
    return Response(
        content=pdf_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
