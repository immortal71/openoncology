"""
Stripe Connect integration for pharma accounts.

Flow:
  1. POST /api/stripe/connect/onboard/{pharma_id}
       → Creates a Stripe Connect Express account (or retrieves existing)
       → Returns an account link URL for the pharma to complete KYC
  2. GET  /api/stripe/connect/return/{pharma_id}
       → Pharma redirected here after completing Stripe onboarding
       → Verifies account details_submitted and saves stripe_account_id
  3. GET  /api/stripe/connect/status/{pharma_id}
       → Returns current Stripe account status
  4. POST /api/stripe/connect/payout/{pharma_id}
       → Triggers a manual payout transfer (admin only, for releasing escrow funds)

All payout transfers use Stripe Connect's destination charges so the pharma
receives funds directly minus Stripe fees.
"""
import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_session
from api.models.pharma import PharmaCompany
from api.routes.auth import get_current_patient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stripe/connect", tags=["stripe-connect"])

stripe.api_key = settings.STRIPE_SECRET_KEY


def _require_admin(claims: dict = Depends(get_current_patient)) -> dict:
    roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="admin role required")
    return claims


# ── Account onboarding ────────────────────────────────────────────────────────

@router.post("/onboard/{pharma_id}")
async def start_onboarding(
    pharma_id: str,
    request: Request,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Create or resume Stripe Connect Express onboarding for a pharma company."""
    company = await db.get(PharmaCompany, pharma_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Create Express account if not yet created
    if not company.stripe_account_id:
        account = stripe.Account.create(
            type="express",
            email=company.contact_email,
            metadata={"pharma_id": pharma_id, "company_name": company.name},
            capabilities={
                "transfers": {"requested": True},
                "card_payments": {"requested": True},
            },
        )
        company.stripe_account_id = account.id
        await db.commit()
        logger.info("Created Stripe Connect account %s for %s", account.id, pharma_id)

    base_url = str(request.base_url).rstrip("/")
    account_link = stripe.AccountLink.create(
        account=company.stripe_account_id,
        refresh_url=f"{base_url}/api/stripe/connect/onboard/{pharma_id}",
        return_url=f"{base_url}/api/stripe/connect/return/{pharma_id}",
        type="account_onboarding",
    )
    return {"onboarding_url": account_link.url}


@router.get("/return/{pharma_id}")
async def onboarding_return(
    pharma_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Stripe redirects the pharma here after completing (or leaving) onboarding."""
    company = await db.get(PharmaCompany, pharma_id)
    if not company or not company.stripe_account_id:
        raise HTTPException(status_code=404, detail="Company not found")

    account = stripe.Account.retrieve(company.stripe_account_id)
    details_submitted = account.get("details_submitted", False)

    return {
        "pharma_id": pharma_id,
        "stripe_account_id": company.stripe_account_id,
        "details_submitted": details_submitted,
        "charges_enabled": account.get("charges_enabled", False),
        "payouts_enabled": account.get("payouts_enabled", False),
    }


# ── Account status ────────────────────────────────────────────────────────────

@router.get("/status/{pharma_id}")
async def account_status(
    pharma_id: str,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Admin: retrieve live Stripe account status for a pharma company."""
    company = await db.get(PharmaCompany, pharma_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not company.stripe_account_id:
        return {"status": "no_account"}

    account = stripe.Account.retrieve(company.stripe_account_id)
    return {
        "stripe_account_id": account.id,
        "details_submitted": account.get("details_submitted"),
        "charges_enabled": account.get("charges_enabled"),
        "payouts_enabled": account.get("payouts_enabled"),
        "requirements": account.get("requirements", {}).get("currently_due", []),
    }


# ── Escrow payout ─────────────────────────────────────────────────────────────

class PayoutRequest:
    def __init__(self, amount_usd: float, description: str = "OpenOncology campaign payout"):
        self.amount_usd = amount_usd
        self.description = description

from pydantic import BaseModel as _BaseModel

class PayoutBody(_BaseModel):
    amount_usd: float
    description: str = "OpenOncology campaign payout"
    campaign_id: str | None = None


@router.post("/payout/{pharma_id}")
async def trigger_payout(
    pharma_id: str,
    body: PayoutBody,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Admin: transfer funds from the platform to a pharma's Connect account.

    Uses Stripe Transfer (platform → Connect account) to release escrow funds
    when a crowdfunding campaign goal is met and a drug order is confirmed.
    """
    company = await db.get(PharmaCompany, pharma_id)
    if not company or not company.stripe_account_id:
        raise HTTPException(status_code=400, detail="Company has no Stripe account")

    amount_cents = int(body.amount_usd * 100)
    if amount_cents < 100:
        raise HTTPException(status_code=400, detail="Minimum payout is $1.00")

    transfer = stripe.Transfer.create(
        amount=amount_cents,
        currency="usd",
        destination=company.stripe_account_id,
        description=body.description,
        metadata={"pharma_id": pharma_id, "campaign_id": body.campaign_id or ""},
    )
    logger.info(
        "Transfer %s: $%.2f → pharma %s (Stripe account %s)",
        transfer.id, body.amount_usd, pharma_id, company.stripe_account_id,
    )
    return {
        "transfer_id": transfer.id,
        "amount_usd": body.amount_usd,
        "destination": company.stripe_account_id,
        "status": transfer.get("reversed", False) and "reversed" or "created",
    }
