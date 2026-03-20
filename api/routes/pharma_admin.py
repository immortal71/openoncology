"""
Pharma onboarding & admin verification routes.

POST /api/pharma/apply          — Pharma company submits application (public)
GET  /api/pharma/applications   — Admin lists pending applications
POST /api/pharma/verify/{id}    — Admin approves/rejects a pharma company
GET  /api/pharma/{id}           — Public profile of a verified pharma company
GET  /api/pharma/               — List all verified pharma companies

Admin role enforcement: token must have realm role "admin".
"""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.pharma import PharmaCompany
from api.routes.auth import get_current_patient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pharma", tags=["pharma"])


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_admin(claims: dict = Depends(get_current_patient)) -> dict:
    roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return claims


# ── Schemas ───────────────────────────────────────────────────────────────────

class PharmaApplyRequest(BaseModel):
    name: str
    description: str
    contact_email: EmailStr
    website: Optional[str] = None
    logo_url: Optional[str] = None
    registration_number: Optional[str] = None   # national pharma reg. number
    country: Optional[str] = None


class PharmaVerifyRequest(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply(body: PharmaApplyRequest, db: AsyncSession = Depends(get_session)):
    """Any pharma company can submit an application. Starts unverified."""
    company = PharmaCompany(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        contact_email=body.contact_email,
        logo_url=body.logo_url,
        verified=False,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    logger.info("Pharma application submitted: %s (%s)", company.name, company.id)
    return {"id": company.id, "status": "pending_review"}


@router.get("/applications")
async def list_applications(
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Admin: list all pharma companies awaiting verification."""
    stmt = select(PharmaCompany).where(PharmaCompany.verified == False).order_by(PharmaCompany.created_at)  # noqa: E712
    companies = (await db.execute(stmt)).scalars().all()
    return [_serialize(c) for c in companies]


@router.post("/verify/{company_id}")
async def verify(
    company_id: str,
    body: PharmaVerifyRequest,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Admin: approve or reject a pharma company application."""
    company = await db.get(PharmaCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.verified = body.approved
    await db.commit()

    action = "approved" if body.approved else "rejected"
    logger.info("Pharma company %s %s by admin", company_id, action)
    return {"id": company_id, "verified": body.approved, "status": action}


@router.get("/")
async def list_verified(db: AsyncSession = Depends(get_session)):
    """Public: list all verified pharma companies."""
    stmt = select(PharmaCompany).where(PharmaCompany.verified == True).order_by(PharmaCompany.name)  # noqa: E712
    companies = (await db.execute(stmt)).scalars().all()
    return [_serialize(c) for c in companies]


@router.get("/{company_id}")
async def get_company(company_id: str, db: AsyncSession = Depends(get_session)):
    """Public: get a single verified pharma company profile."""
    company = await db.get(PharmaCompany, company_id)
    if not company or not company.verified:
        raise HTTPException(status_code=404, detail="Company not found")
    return _serialize(company)


def _serialize(c: PharmaCompany) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "contact_email": c.contact_email,
        "logo_url": c.logo_url,
        "verified": c.verified,
        "stripe_account_id": c.stripe_account_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
