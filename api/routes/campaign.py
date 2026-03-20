"""
Full crowdfunding campaign lifecycle management.

Extends the existing crowdfund route with:
  POST /api/crowdfund/               — create campaign (auth required)
  GET  /api/crowdfund/{slug}         — public view (already in crowdfund.py)
  POST /api/crowdfund/{slug}/donate  — anonymous Stripe donation intent
  POST /api/crowdfund/{slug}/activate — patient activates/publishes campaign
  POST /api/crowdfund/{slug}/close   — patient or admin closes campaign
  POST /api/crowdfund/{slug}/complete — admin marks campaign goal reached
                                        and triggers pharma payout

Milestone webhook:
  - When raised_usd crosses 25%, 50%, 75%, 100% of goal_usd it dispatches
    a Celery task to send a milestone email to the campaign owner.
"""
import re
import uuid
import logging
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_session
from api.models.campaign import Campaign
from api.models.patient import Patient
from api.routes.auth import get_current_patient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crowdfund", tags=["crowdfund"])
stripe.api_key = settings.STRIPE_SECRET_KEY

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MILESTONES = [25, 50, 75, 100]


# ── Schemas ───────────────────────────────────────────────────────────────────

class CampaignCreateRequest(BaseModel):
    title: str
    slug: str = Field(..., pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    patient_story: str
    goal_usd: float = Field(..., gt=0)
    submission_id: Optional[str] = None


class DonateRequest(BaseModel):
    amount_usd: float = Field(..., gt=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_campaign_or_404(slug: str, db: AsyncSession) -> Campaign:
    stmt = select(Campaign).where(Campaign.slug == slug)
    campaign = (await db.execute(stmt)).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _campaign_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "slug": c.slug,
        "patient_story": c.patient_story,
        "goal_usd": c.goal_usd,
        "raised_usd": c.raised_usd or 0,
        "percent_complete": c.percent_complete or 0,
        "status": c.status if hasattr(c, "status") else "active",
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _check_milestone(old_raised: float, new_raised: float, goal_usd: float, campaign_id: str):
    """Dispatch milestone notify tasks when crossing 25/50/75/100%."""
    if goal_usd <= 0:
        return
    for pct in _MILESTONES:
        threshold = goal_usd * pct / 100
        if old_raised < threshold <= new_raised:
            try:
                from workers.notify_worker import notify_campaign_milestone
                notify_campaign_milestone.apply_async(
                    args=[campaign_id, pct],
                    queue="notify",
                )
                logger.info("Campaign %s crossed %d%% milestone", campaign_id, pct)
            except Exception as exc:
                logger.warning("Milestone notify failed: %s", exc)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreateRequest,
    claims: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_session),
):
    """Create a new crowdfunding campaign (patient must be authenticated)."""
    # Verify slug is unique
    existing = (await db.execute(select(Campaign).where(Campaign.slug == body.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")

    # Find patient record
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == claims["sub"])
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    campaign = Campaign(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        submission_id=body.submission_id,
        title=body.title,
        slug=body.slug,
        patient_story=body.patient_story,
        goal_usd=body.goal_usd,
        raised_usd=0.0,
        percent_complete=0.0,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return _campaign_dict(campaign)


@router.get("/{slug}")
async def get_campaign(slug: str, db: AsyncSession = Depends(get_session)):
    """Public: view a campaign by slug."""
    campaign = await _get_campaign_or_404(slug, db)
    return _campaign_dict(campaign)


@router.post("/{slug}/donate")
async def donate(
    slug: str,
    body: DonateRequest,
    db: AsyncSession = Depends(get_session),
):
    """Create a Stripe PaymentIntent for a donation. No auth required."""
    campaign = await _get_campaign_or_404(slug, db)
    amount_cents = int(body.amount_usd * 100)

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        automatic_payment_methods={"enabled": True},
        metadata={
            "type": "donation",
            "campaign_id": campaign.id,
            "campaign_slug": slug,
        },
        description=f"Donation to campaign: {campaign.title}",
    )
    return {"client_secret": intent.client_secret}


@router.post("/{slug}/activate")
async def activate_campaign(
    slug: str,
    claims: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_session),
):
    """Patient publishes (activates) their campaign so donations can be received."""
    campaign = await _get_campaign_or_404(slug, db)
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == claims["sub"])
    )).scalar_one_or_none()

    if not patient or campaign.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    # Status tracked in a new column — add gracefully
    if hasattr(campaign, "status"):
        campaign.status = "active"
    await db.commit()
    return {"id": campaign.id, "slug": slug, "status": "active"}


@router.post("/{slug}/close")
async def close_campaign(
    slug: str,
    claims: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_session),
):
    """Patient or admin closes a campaign (no more donations accepted)."""
    campaign = await _get_campaign_or_404(slug, db)
    roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == claims["sub"])
    )).scalar_one_or_none()

    is_owner = patient and campaign.patient_id == patient.id
    is_admin = "admin" in roles
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorised")

    if hasattr(campaign, "status"):
        campaign.status = "closed"
    await db.commit()
    return {"id": campaign.id, "slug": slug, "status": "closed"}


@router.post("/{slug}/complete")
async def complete_campaign(
    slug: str,
    pharma_id: str,
    claims: dict = Depends(get_current_patient),
    db: AsyncSession = Depends(get_session),
):
    """Admin: mark goal reached and trigger pharma payout via Stripe Transfer."""
    roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="admin role required")

    campaign = await _get_campaign_or_404(slug, db)

    from api.models.pharma import PharmaCompany
    pharma = await db.get(PharmaCompany, pharma_id)
    if not pharma or not pharma.stripe_account_id:
        raise HTTPException(status_code=400, detail="Pharma company has no Stripe account")

    amount_cents = int((campaign.raised_usd or 0) * 100)
    if amount_cents < 100:
        raise HTTPException(status_code=400, detail="No funds to transfer")

    transfer = stripe.Transfer.create(
        amount=amount_cents,
        currency="usd",
        destination=pharma.stripe_account_id,
        description=f"Campaign payout: {campaign.title}",
        metadata={"campaign_id": campaign.id, "pharma_id": pharma_id},
    )

    if hasattr(campaign, "status"):
        campaign.status = "complete"
    await db.commit()

    logger.info(
        "Campaign %s complete — transferred $%.2f to %s (transfer %s)",
        campaign.id, campaign.raised_usd, pharma.stripe_account_id, transfer.id,
    )
    return {
        "campaign_id": campaign.id,
        "transfer_id": transfer.id,
        "amount_usd": campaign.raised_usd,
        "status": "complete",
    }
