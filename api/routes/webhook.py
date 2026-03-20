"""Stripe webhook handler.

POST /api/webhook/stripe

Verifies Stripe-Signature header with STRIPE_WEBHOOK_SECRET.
Handles:
  - payment_intent.succeeded  →  update Order.status = "confirmed"
     (if metadata.type == "donation"  →  increment Campaign.raised_usd)
  - payment_intent.payment_failed  →  update Order.status = "failed"
"""
import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_session
from api.models.order import Order
from api.models.campaign import Campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_type: str = event["type"]
    obj = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        await _handle_succeeded(obj, db)
    elif event_type == "payment_intent.payment_failed":
        await _handle_failed(obj, db)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)

    return {"received": True}


async def _handle_succeeded(pi: dict, db: AsyncSession) -> None:
    pi_id: str = pi["id"]
    metadata: dict = pi.get("metadata", {})

    if metadata.get("type") == "donation":
        campaign_id = metadata.get("campaign_id")
        amount_usd = pi["amount_received"] / 100  # Stripe uses cents
        if campaign_id:
            campaign = await db.get(Campaign, campaign_id)
            if campaign:
                campaign.raised_usd = (campaign.raised_usd or 0) + amount_usd
                if campaign.goal_usd and campaign.goal_usd > 0:
                    campaign.percent_complete = round(
                        (campaign.raised_usd / campaign.goal_usd) * 100, 2
                    )
                await db.commit()
                logger.info("Campaign %s: +$%.2f → $%.2f raised", campaign_id, amount_usd, campaign.raised_usd)
        return

    # Regular marketplace order
    stmt = select(Order).where(Order.stripe_pi_id == pi_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order:
        order.status = "confirmed"
        await db.commit()
        logger.info("Order %s confirmed via Stripe PI %s", order.id, pi_id)


async def _handle_failed(pi: dict, db: AsyncSession) -> None:
    pi_id: str = pi["id"]
    stmt = select(Order).where(Order.stripe_pi_id == pi_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order:
        order.status = "failed"
        await db.commit()
        logger.warning("Order %s payment failed (PI %s)", order.id, pi_id)
