"""Stripe webhook handler.

POST /api/webhook/stripe

Verifies Stripe-Signature header with STRIPE_WEBHOOK_SECRET.

Every event id is recorded in stripe_webhook_events before any handler runs, and
a repeat is acknowledged without being processed again. Stripe redelivers on any
non-2xx, on a timeout, and at its own discretion, so this is ordinary traffic.

Handles:
  - payment_intent.succeeded  →  update Order.status = "confirmed"
     (if metadata.type == "donation"  →  increment Campaign.raised_usd)
  - payment_intent.payment_failed  →  update Order.status = "failed"
"""
import logging
import stripe
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.order import Order, OrderStatus
from models.campaign import Campaign
from models.stripe_event import StripeWebhookEvent
from utils.http import bad_request_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])
stripe.api_key = settings.stripe_secret_key


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise bad_request_error(request, "Invalid Stripe signature")
    except Exception:
        # Logged rather than swallowed. Every failure here answered Stripe with
        # "Invalid webhook payload", including a bug in our own parsing, and
        # Stripe retries a non-2xx, so a defect on this path became an
        # indefinite retry loop with no record of the actual cause.
        logger.exception("[stripe] webhook payload could not be parsed")
        raise bad_request_error(request, "Invalid webhook payload")

    event_id: str = event["id"]
    event_type: str = event["type"]
    obj = event["data"]["object"]

    # Stripe guarantees at-least-once delivery, so a repeat is normal traffic
    # rather than an error. Claim the event id before doing any work: the
    # primary key rejects the second writer, which makes every branch below
    # replay-safe at once instead of each one having to be individually safe.
    if not await _claim_event(event_id, event_type, db):
        logger.info("[stripe] event %s already processed, skipping", event_id)
        return {"received": True, "duplicate": True}

    if event_type == "payment_intent.succeeded":
        await _handle_succeeded(obj, db)
    elif event_type == "payment_intent.payment_failed":
        await _handle_failed(obj, db)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)

    return {"received": True}


async def _claim_event(event_id: str, event_type: str, db: AsyncSession) -> bool:
    """Record this event id. False if some earlier delivery already did.

    Committed on its own, before the handlers run. If a handler then fails, the
    event stays claimed and is not retried, which is the correct trade for the
    donation path: a redelivery there adds money that was never paid, and that
    error is neither visible nor reversible from the campaign total. A handler
    failure is at least recorded in the log with its traceback.
    """
    db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        return False


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
                await db.commit()
                logger.info("Campaign %s: +$%.2f → $%.2f raised", campaign_id, amount_usd, campaign.raised_usd)
        return

    # Regular marketplace order
    stmt = select(Order).where(Order.stripe_payment_intent_id == pi_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order:
        order.status = OrderStatus.confirmed
        await db.commit()
        logger.info("Order %s confirmed via Stripe PI %s", order.id, pi_id)


async def _handle_failed(pi: dict, db: AsyncSession) -> None:
    pi_id: str = pi["id"]
    stmt = select(Order).where(Order.stripe_payment_intent_id == pi_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order:
        order.status = OrderStatus.failed
        await db.commit()
        logger.warning("Order %s payment failed (PI %s)", order.id, pi_id)
