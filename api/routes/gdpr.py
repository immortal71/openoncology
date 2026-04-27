"""
GDPR Endpoints (Article 17 — Right to Erasure / Right to Access).

DELETE /api/me        — patient requests account deletion (queues gdpr_worker task)
GET    /api/me/export — patient downloads a JSON export of all their data
"""
import logging
import uuid
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.auth import get_current_patient
from models.patient import Patient
from models.deletion_request import DeletionRequest
from workers.gdpr_worker import erase_patient_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["gdpr"])


# ── GET /api/me/export ────────────────────────────────────────────────────────

@router.get("/export", summary="Export all personal data (GDPR Art. 20)")
async def export_my_data(
    current_user: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    """Return a machine-readable JSON export of all data held for this user."""
    keycloak_id: str = current_user["sub"]

    patient = await db.scalar(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found")

    from models.submission import Submission
    from models.mutation import Mutation
    from models.repurposing import RepurposingCandidate
    from models.result import Result
    from models.order import Order
    from models.campaign import Campaign

    submissions = (await db.scalars(
        select(Submission).where(Submission.patient_id == patient.id)
    )).all()
    submission_ids = [s.id for s in submissions]

    mutations = (await db.scalars(
        select(Mutation).where(Mutation.submission_id.in_(submission_ids))
    )).all() if submission_ids else []

    results = (await db.scalars(
        select(Result).where(Result.submission_id.in_(submission_ids))
    )).all() if submission_ids else []
    result_ids = [r.id for r in results]

    candidates = (await db.scalars(
        select(RepurposingCandidate).where(RepurposingCandidate.result_id.in_(result_ids))
    )).all() if result_ids else []

    orders = (await db.scalars(
        select(Order).where(Order.patient_id == patient.id)
    )).all()

    campaigns = (await db.scalars(
        select(Campaign).where(Campaign.patient_id == patient.id)
    )).all()

    def _row(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "patient": _row(patient),
        "submissions": [_row(s) for s in submissions],
        "mutations": [_row(m) for m in mutations],
        "repurposing_candidates": [_row(c) for c in candidates],
        "results": [_row(r) for r in results],
        "orders": [_row(o) for o in orders],
        "campaigns": [_row(c) for c in campaigns],
    }


# ── DELETE /api/me ────────────────────────────────────────────────────────────

@router.delete(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request account deletion (GDPR Art. 17)",
)
async def request_deletion(
    current_user: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue erasure of all personal data.  Deletion is performed asynchronously
    by the gdpr_worker within 30 days per GDPR requirements, but typically
    completes within minutes.  Returns a deletion request ID for tracking.
    """
    keycloak_id: str = current_user["sub"]

    patient = await db.scalar(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found")

    # Idempotency — don't allow duplicate pending requests
    existing = await db.scalar(
        select(DeletionRequest).where(
            DeletionRequest.patient_id == patient.id,
            DeletionRequest.status == "pending",
        )
    )
    if existing:
        return {"deletion_request_id": str(existing.id), "status": "pending", "message": "Deletion already queued"}

    req = DeletionRequest(
        id=uuid.uuid4(),
        patient_id=patient.id,
        keycloak_id=keycloak_id,
        requested_at=datetime.now(UTC),
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    erase_patient_data.apply_async(
        kwargs={"deletion_request_id": str(req.id)},
        queue="notify",
    )

    logger.info("[gdpr] Deletion queued for patient %s (request %s)", patient.id, req.id)

    return {
        "deletion_request_id": str(req.id),
        "status": "pending",
        "message": "Your data will be erased within 30 days. You will receive a confirmation email.",
    }
