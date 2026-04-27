"""Pharma bid model — competitive bidding on custom drug orders.

When a patient requests a custom drug synthesis, pharma companies can submit
bids with their price and estimated timeline.  The patient selects a winning
bid and proceeds to payment.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, Text, Enum as SAEnum, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class BidStatus(str, enum.Enum):
    open = "open"        # bidding is open — pharma can submit bids
    accepted = "accepted"  # patient accepted this bid
    rejected = "rejected"  # patient rejected this bid
    expired = "expired"  # auction closed with no winner


class DiscoveryStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class PharmaBid(Base):
    __tablename__ = "pharma_bids"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # The custom drug request this bid is for
    drug_request_id: Mapped[str] = mapped_column(
        ForeignKey("drug_requests.id"), nullable=False
    )

    # Which pharma company submitted this bid
    pharma_id: Mapped[str] = mapped_column(
        ForeignKey("pharma_companies.id"), nullable=False
    )

    # Bid details
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    status: Mapped[BidStatus] = mapped_column(SAEnum(BidStatus), default=BidStatus.open)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pharma: Mapped["PharmaCompany"] = relationship("PharmaCompany")
    drug_request: Mapped["DrugRequest"] = relationship("DrugRequest", back_populates="bids")


class DrugRequest(Base):
    """A patient's open request for custom drug synthesis.

    Posted to the marketplace so pharma companies can bid on it.
    Stores the drug specification derived from the patient's AI analysis result.
    """
    __tablename__ = "drug_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)
    result_id: Mapped[str] = mapped_column(ForeignKey("results.id"), nullable=True)

    # Drug specification — mutation, target gene, compound requirements
    target_gene: Mapped[str] = mapped_column(String(64), nullable=True)
    drug_spec: Mapped[str] = mapped_column(Text, nullable=False)

    # Budget ceiling the patient is willing to pay
    max_budget_usd: Mapped[float] = mapped_column(Float, nullable=True)

    # Discovery generation state for custom-drug brief production
    discovery_status: Mapped[DiscoveryStatus] = mapped_column(
        SAEnum(DiscoveryStatus), default=DiscoveryStatus.queued, nullable=False
    )
    discovery_brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discovery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovery_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Whether the request is visible to pharma companies
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Winning bid (set when patient accepts a bid)
    accepted_bid_id: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")
    bids: Mapped[list["PharmaBid"]] = relationship("PharmaBid", back_populates="drug_request")
