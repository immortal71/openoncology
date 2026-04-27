import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class OrderStatus(str, enum.Enum):
    pending = "pending"
    payment_processing = "payment_processing"
    confirmed = "confirmed"
    failed = "failed"
    manufacturing = "manufacturing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)
    pharma_id: Mapped[str] = mapped_column(ForeignKey("pharma_companies.id"), nullable=False)

    # Drug specification — what compound, dose, formulation
    drug_spec: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.pending)

    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)

    # Stripe payment intent ID
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="orders")
    pharma: Mapped["PharmaCompany"] = relationship("PharmaCompany", back_populates="orders")
