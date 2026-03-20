"""
Crowdfund route — create and manage patient fundraising campaigns.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import stripe

from config import settings
from database import get_db
from models.campaign import Campaign
from models.patient import Patient
from routes.auth import get_current_patient

router = APIRouter(prefix="/api/crowdfund", tags=["crowdfund"])

stripe.api_key = settings.stripe_secret_key

_SLUG_RE = re.compile(r"^[a-z0-9-]{3,64}$")


class CampaignCreate(BaseModel):
    slug: str = Field(..., min_length=3, max_length=64)
    title: str = Field(..., max_length=256)
    patient_story: str = Field(..., max_length=5000)
    goal_usd: float = Field(..., gt=0, le=1_000_000)
    is_public: bool = True
    result_id: str | None = None
    order_id: str | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    req: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    if not _SLUG_RE.match(req.slug):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Slug must be 3-64 lowercase letters, numbers, or hyphens.",
        )

    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    existing = (await db.execute(
        select(Campaign).where(Campaign.slug == req.slug)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This campaign URL is already taken. Please choose another.",
        )

    campaign = Campaign(
        patient_id=patient.id,
        slug=req.slug,
        title=req.title,
        patient_story=req.patient_story,
        goal_usd=req.goal_usd,
        is_public=req.is_public,
        result_id=req.result_id,
        order_id=req.order_id,
    )
    db.add(campaign)
    await db.commit()

    return {
        "campaign_id": campaign.id,
        "url": f"/fund/{campaign.slug}",
        "goal_usd": campaign.goal_usd,
        "raised_usd": campaign.raised_usd,
        "is_public": campaign.is_public,
    }


@router.get("/{slug}")
async def get_campaign(slug: str, db: AsyncSession = Depends(get_db)):
    """Public campaign page — no auth required for public campaigns."""
    campaign = (await db.execute(
        select(Campaign).where(Campaign.slug == slug, Campaign.is_public == True, Campaign.is_active == True)
    )).scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    return {
        "campaign_id": campaign.id,
        "slug": campaign.slug,
        "title": campaign.title,
        "patient_story": campaign.patient_story,
        "goal_usd": campaign.goal_usd,
        "raised_usd": campaign.raised_usd,
        "percent_complete": round((campaign.raised_usd / campaign.goal_usd) * 100, 1),
    }


class DonationRequest(BaseModel):
    amount_usd: float = Field(..., gt=0, le=100_000)


@router.post("/{slug}/donate")
async def donate_to_campaign(
    slug: str,
    req: DonationRequest,
    db: AsyncSession = Depends(get_db),
):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.slug == slug, Campaign.is_public == True, Campaign.is_active == True)
    )).scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    # Create a Stripe payment intent for the donation
    intent = stripe.PaymentIntent.create(
        amount=int(req.amount_usd * 100),
        currency="usd",
        metadata={"campaign_id": campaign.id, "type": "donation"},
    )

    return {
        "client_secret": intent["client_secret"],
        "amount_usd": req.amount_usd,
        "campaign_title": campaign.title,
    }
