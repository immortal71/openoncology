import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PharmaCompany(Base):
    __tablename__ = "pharma_companies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    contact_email: Mapped[str] = mapped_column(String(256), nullable=False)

    # Verified by platform admin before appearing in marketplace
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    min_order_usd: Mapped[float] = mapped_column(Float, nullable=True)

    # Stripe Connect ID for receiving payouts
    stripe_account_id: Mapped[str] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="pharma")
