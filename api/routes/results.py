"""
Results route — return mutation analysis report for a submission.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.submission import Submission
from models.patient import Patient
from models.mutation import Mutation
from routes.auth import get_current_patient
from services.storage import generate_presigned_download_url
from config import settings

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{submission_id}/structure")
async def get_structure_url(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """
    Returns a presigned S3/MinIO URL for the 3D protein structure (AlphaFold).
    """
    keycloak_id = token_payload.get("sub")

    # Ensure the submission belongs to this patient
    submission = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(
            Submission.id == submission_id,
            Patient.keycloak_id == keycloak_id,
        )
        .options(selectinload(Submission.mutations))
    )).scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    # Find the first mutation with a valid structure path
    mutation = next((m for m in submission.mutations if m.alphafold_structure_path), None)

    if not mutation or not mutation.alphafold_structure_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="3D structure not yet available for this mutation.",
        )

    # Generate presigned URL from the processed bucket
    url = generate_presigned_download_url(
        key=mutation.alphafold_structure_path,
        bucket=settings.bucket_processed,
        expires_in=3600,
    )

    return {"url": url}


@router.get("/{submission_id}")
async def get_results(
    submission_id: str,
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
            "message": "Analysis still in progress. Check back soon.",
        }

    result = submission.result
    mutations = submission.mutations

    return {
        "submission_id": submission_id,
        "cancer_type": submission.cancer_type,
        "status": "complete",
        "has_targetable_mutation": result.has_targetable_mutation if result else False,
        "target_gene": result.target_gene if result else None,
        "summary": result.summary_text if result else None,
        "plain_language_summary": result.plain_language_summary if result else None,
        "cbioportal_data": result.cbioportal_data if result else None,
        "cosmic_sample_count": result.cosmic_sample_count if result else None,
        "oncologist_reviewed": result.oncologist_reviewed if result else False,
        "oncologist_notes": result.oncologist_notes if result else None,
        "mutations": [
            {
                "gene": m.gene,
                "mutation_type": m.mutation_type,
                "hgvs": m.hgvs_notation,
                "classification": m.classification,
                "oncokb_level": m.oncokb_level,
                "is_targetable": m.is_targetable,
                "alphamissense_score": m.alphamissense_score,
            }
            for m in mutations
        ],
        "result_id": result.id if result else None,
    }


@router.get("/dashboard/all")
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
