"""Oncologist portal routes.

GET  /api/oncologist/pending  — list results awaiting review (oncologist role required)
POST /api/oncologist/review   — approve or flag a result
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.result import Result
from models.submission import Submission
from models.mutation import Mutation
from routes.auth import get_current_patient

router = APIRouter(prefix="/api/oncologist", tags=["oncologist"])


def _require_oncologist(claims: dict = Depends(get_current_patient)) -> dict:
    """Raise 403 if token lacks the 'oncologist' realm role."""
    roles: list[str] = (
        claims.get("realm_access", {}).get("roles", [])
    )
    if "oncologist" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="oncologist role required",
        )
    return claims


class ReviewRequest(BaseModel):
    submission_id: str
    approved: bool
    notes: str = ""


@router.get("/pending")
async def list_pending(
    _: dict = Depends(_require_oncologist),
    db: AsyncSession = Depends(get_db),
):
    """Return submissions whose result has not yet been oncologist-reviewed."""
    stmt = (
        select(Result, Submission)
        .join(Submission, Result.submission_id == Submission.id)
        .where(Result.oncologist_reviewed == False)  # noqa: E712
    )
    rows = (await db.execute(stmt)).all()

    output = []
    for result, submission in rows:
        # Count mutations
        mut_count = (
            await db.scalar(
                select(func.count())
                .select_from(Mutation)
                .where(Mutation.submission_id == submission.id)
            )
        )
        targetable_count = (
            await db.scalar(
                select(func.count())
                .select_from(Mutation)
                .where(
                    Mutation.submission_id == submission.id,
                    Mutation.is_targetable == True,  # noqa: E712
                )
            )
        )

        output.append(
            {
                "submission_id": submission.id,
                "patient_email_hash": None,  # deliberately hidden
                "mutation_count": mut_count or 0,
                "targetable_count": targetable_count or 0,
                "created_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            }
        )

    return output


@router.post("/review", status_code=status.HTTP_200_OK)
async def submit_review(
    body: ReviewRequest,
    _: dict = Depends(_require_oncologist),
    db: AsyncSession = Depends(get_db),
):
    """Mark a result as reviewed and save oncologist notes."""
    result = (await db.execute(
        select(Result).where(Result.submission_id == body.submission_id)
    )).scalar_one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    result.oncologist_reviewed = True
    result.oncologist_notes = body.notes
    if not body.approved:
        result.oncologist_notes = f"[FLAGGED] {body.notes}"

    await db.commit()
    return {"status": "ok", "submission_id": body.submission_id}
