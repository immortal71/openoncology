"""
Repurposing route — return AI-ranked drug repurposing candidates for a result.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.result import Result
from models.submission import Submission
from models.patient import Patient
from routes.auth import get_current_patient

router = APIRouter(prefix="/api/repurposing", tags=["repurposing"])


@router.get("/{result_id}")
async def get_repurposing_candidates(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")

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
