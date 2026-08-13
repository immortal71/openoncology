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
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel as _BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.pharma import PharmaCompany
from routes.auth import get_current_patient
from utils.http import bad_request_error, not_found_error
from middleware.rate_limit import limiter, READ_LIMIT, WRITE_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stripe/connect", tags=["stripe-connect"])

stripe.api_key = settings.stripe_secret_key


def _require_admin(claims: dict = Depends(get_current_patient)) -> dict:
    roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="admin role required")
    return claims


# ── Account onboarding ────────────────────────────────────────────────────────

@router.post("/onboard/{pharma_id}")
@limiter.limit(WRITE_LIMIT)
async def start_onboarding(
    pharma_id: str,
    request: Request,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create or resume Stripe Connect Express onboarding for a pharma company."""
    company = await db.get(PharmaCompany, pharma_id)
    if not company:
        raise not_found_error(request, "Company not found")

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
@limiter.limit(READ_LIMIT)
async def onboarding_return(
    pharma_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stripe redirects the pharma's browser here after onboarding.

    Deliberately unauthenticated, and it has to stay that way: this is the
    `return_url` handed to `stripe.AccountLink.create`, so Stripe sends the
    browser here directly and there is no Authorization header to check. Adding
    `_require_admin` would 403 every pharma the moment they finish KYC.

    What it must not do is answer questions. It previously returned
    `stripe_account_id`, `charges_enabled` and `payouts_enabled` for whatever
    id appeared in the path, with no credential of any kind, which made it an
    oracle: walk the ids and read back the Stripe account and payout state of
    every company on the platform. It also 404'd on unknown ids and 200'd on
    known ones, so it confirmed which ids existed even before the body was read.

    It now returns the same shape either way and says only whether onboarding
    finished. Everything it used to disclose is available from
    `GET /status/{pharma_id}`, which requires the admin role.
    """
    company = await db.get(PharmaCompany, pharma_id)

    details_submitted = False
    if company and company.stripe_account_id:
        try:
            account = stripe.Account.retrieve(company.stripe_account_id)
            details_submitted = bool(account.get("details_submitted", False))
        except Exception:
            # A Stripe outage must not turn this into an error oracle either:
            # the response shape stays identical.
            logger.exception(
                "[stripe] account retrieve failed during onboarding return"
            )

    # Uniform response. No account id, no capability flags, and no distinction
    # between "unknown company" and "known company that has not finished".
    return {
        "onboarding_complete": details_submitted,
        "detail": (
            "Onboarding complete."
            if details_submitted
            else "Onboarding is not complete. Return to the dashboard to continue."
        ),
    }


# ── Account status ────────────────────────────────────────────────────────────

@router.get("/status/{pharma_id}")
@limiter.limit(READ_LIMIT)
async def account_status(
    pharma_id: str,
    request: Request,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: retrieve live Stripe account status for a pharma company."""
    company = await db.get(PharmaCompany, pharma_id)
    if not company:
        raise not_found_error(request, "Company not found")

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

class PayoutBody(_BaseModel):
    amount_usd: float
    description: str = "OpenOncology campaign payout"
    campaign_id: str | None = None


@router.post("/payout/{pharma_id}")
@limiter.limit(WRITE_LIMIT)
async def trigger_payout(
    pharma_id: str,
    body: PayoutBody,
    request: Request,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: transfer funds from the platform to a pharma's Connect account.

    Uses Stripe Transfer (platform → Connect account) to release escrow funds
    when a crowdfunding campaign goal is met and a drug order is confirmed.
    """
    company = await db.get(PharmaCompany, pharma_id)
    if not company or not company.stripe_account_id:
        raise bad_request_error(request, "Company has no Stripe account")

    amount_cents = int(body.amount_usd * 100)
    if amount_cents < 100:
        raise bad_request_error(request, "Minimum payout is $1.00")

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
