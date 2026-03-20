"""
Marketplace route — pharma company listings, drug ordering, and competitive bidding.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import stripe

from config import settings
from database import get_db
from models.pharma import PharmaCompany
from models.order import Order, OrderStatus
from models.patient import Patient
from models.bid import DrugRequest, PharmaBid, BidStatus
from routes.auth import get_current_patient

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

stripe.api_key = settings.stripe_secret_key


@router.get("/pharma")
async def list_pharma_companies(
    db: AsyncSession = Depends(get_db),
):
    """Public list of verified pharma manufacturers."""
    companies = (await db.execute(
        select(PharmaCompany).where(PharmaCompany.verified == True)
    )).scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "country": c.country,
            "description": c.description,
            "min_order_usd": c.min_order_usd,
        }
        for c in companies
    ]


class OrderRequest(BaseModel):
    pharma_id: str
    drug_spec: str = Field(..., max_length=2000)
    amount_usd: float = Field(..., gt=0, le=1_000_000)


@router.post("/order", status_code=status.HTTP_201_CREATED)
async def create_order(
    req: OrderRequest,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")

    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    pharma = (await db.execute(
        select(PharmaCompany).where(
            PharmaCompany.id == req.pharma_id,
            PharmaCompany.verified == True,
        )
    )).scalar_one_or_none()
    if not pharma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pharma company not found.")

    # Create Stripe payment intent
    intent = stripe.PaymentIntent.create(
        amount=int(req.amount_usd * 100),  # cents
        currency="usd",
        metadata={
            "patient_id": patient.id,
            "pharma_id": pharma.id,
        },
    )

    order = Order(
        patient_id=patient.id,
        pharma_id=pharma.id,
        drug_spec=req.drug_spec,
        amount_usd=req.amount_usd,
        status=OrderStatus.payment_processing,
        stripe_payment_intent_id=intent["id"],
    )
    db.add(order)
    await db.commit()

    return {
        "order_id": order.id,
        "client_secret": intent["client_secret"],
        "amount_usd": req.amount_usd,
        "status": order.status,
    }


# ---------------------------------------------------------------------------
# Competitive bidding — custom drug requests & pharma bids
# ---------------------------------------------------------------------------

class DrugRequestCreate(BaseModel):
    drug_spec: str = Field(..., min_length=20, max_length=4000,
                           description="Technical drug specification derived from AI analysis")
    target_gene: str = Field(None, max_length=64)
    max_budget_usd: float = Field(None, gt=0, le=10_000_000)
    result_id: str = Field(None, description="Result ID linking this request to an AI analysis")


@router.post("/drug-requests", status_code=status.HTTP_201_CREATED)
async def create_drug_request(
    req: DrugRequestCreate,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Patient opens a competitive drug synthesis request visible to all verified pharma."""
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    drug_request = DrugRequest(
        patient_id=patient.id,
        result_id=req.result_id,
        target_gene=req.target_gene,
        drug_spec=req.drug_spec,
        max_budget_usd=req.max_budget_usd,
        is_open=True,
    )
    db.add(drug_request)
    await db.commit()
    await db.refresh(drug_request)
    return {"drug_request_id": drug_request.id, "status": "open"}


@router.get("/drug-requests")
async def list_drug_requests(
    db: AsyncSession = Depends(get_db),
):
    """Public listing of open drug synthesis requests for pharma companies to bid on."""
    requests = (await db.execute(
        select(DrugRequest).where(DrugRequest.is_open == True)  # noqa: E712
    )).scalars().all()
    return [
        {
            "id": r.id,
            "target_gene": r.target_gene,
            "drug_spec": r.drug_spec,
            "max_budget_usd": r.max_budget_usd,
            "bid_count": 0,  # populated in detailed view
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]


class BidCreate(BaseModel):
    price_usd: float = Field(..., gt=0, le=10_000_000)
    estimated_weeks: int = Field(..., gt=0, le=520)
    notes: str = Field(None, max_length=2000)


@router.post("/drug-requests/{request_id}/bids", status_code=status.HTTP_201_CREATED)
async def submit_bid(
    request_id: str,
    bid: BidCreate,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Pharma company submits a bid on an open drug request.

    The pharma company must be verified and have a linked Stripe account.
    Auth token must belong to the pharma admin account.
    """
    keycloak_id = token_payload.get("sub")

    pharma = (await db.execute(
        select(PharmaCompany).where(
            PharmaCompany.contact_email == token_payload.get("email"),
            PharmaCompany.verified == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not pharma:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified pharma companies can submit bids.",
        )

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.is_open == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found or closed.")

    # Validate budget ceiling
    if drug_request.max_budget_usd and bid.price_usd > drug_request.max_budget_usd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bid exceeds patient's budget ceiling of ${drug_request.max_budget_usd:,.2f}.",
        )

    new_bid = PharmaBid(
        drug_request_id=request_id,
        pharma_id=pharma.id,
        price_usd=bid.price_usd,
        estimated_weeks=str(bid.estimated_weeks),
        notes=bid.notes,
        status=BidStatus.open,
    )
    db.add(new_bid)
    await db.commit()
    await db.refresh(new_bid)
    return {"bid_id": new_bid.id, "status": "open", "price_usd": bid.price_usd}


@router.get("/drug-requests/{request_id}/bids")
async def list_bids(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return all bids on a drug request.  Only the requesting patient can see bids."""
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=407, detail="Patient not found.")

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.patient_id == patient.id,
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found.")

    bids = (await db.execute(
        select(PharmaBid).where(PharmaBid.drug_request_id == request_id)
    )).scalars().all()

    return [
        {
            "id": b.id,
            "pharma_id": b.pharma_id,
            "price_usd": b.price_usd,
            "estimated_weeks": b.estimated_weeks,
            "notes": b.notes,
            "status": b.status,
            "created_at": b.created_at.isoformat(),
        }
        for b in bids
    ]


@router.post("/drug-requests/{request_id}/bids/{bid_id}/accept")
async def accept_bid(
    request_id: str,
    bid_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Patient accepts a bid, closing the request and rejecting all other bids.

    Returns a Stripe payment intent to collect payment for the accepted bid.
    """
    keycloak_id = token_payload.get("sub")
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    drug_request = (await db.execute(
        select(DrugRequest).where(
            DrugRequest.id == request_id,
            DrugRequest.patient_id == patient.id,
            DrugRequest.is_open == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not drug_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug request not found or already closed.")

    winning_bid = (await db.execute(
        select(PharmaBid).where(
            PharmaBid.id == bid_id,
            PharmaBid.drug_request_id == request_id,
            PharmaBid.status == BidStatus.open,
        )
    )).scalar_one_or_none()
    if not winning_bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found.")

    pharma = (await db.execute(
        select(PharmaCompany).where(PharmaCompany.id == winning_bid.pharma_id)
    )).scalar_one_or_none()

    # Create Stripe payment intent
    transfer_data = {}
    if pharma and pharma.stripe_account_id:
        transfer_data = {"transfer_data": {"destination": pharma.stripe_account_id}}

    intent = stripe.PaymentIntent.create(
        amount=int(winning_bid.price_usd * 100),
        currency="usd",
        metadata={
            "patient_id": patient.id,
            "bid_id": winning_bid.id,
            "drug_request_id": drug_request.id,
        },
        **transfer_data,
    )

    # Atomically close the auction: accept winner, reject all others
    all_bids = (await db.execute(
        select(PharmaBid).where(PharmaBid.drug_request_id == request_id)
    )).scalars().all()

    for b in all_bids:
        b.status = BidStatus.accepted if b.id == bid_id else BidStatus.rejected

    drug_request.is_open = False
    drug_request.accepted_bid_id = bid_id
    drug_request.closed_at = datetime.utcnow()
    await db.commit()

    return {
        "bid_id": bid_id,
        "price_usd": winning_bid.price_usd,
        "estimated_weeks": winning_bid.estimated_weeks,
        "client_secret": intent["client_secret"],
        "status": "accepted",
    }
