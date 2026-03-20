import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)
    result_id: Mapped[str] = mapped_column(ForeignKey("results.id"), unique=True, nullable=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=True)

    # URL slug — e.g. openoncology.org/fund/maya-sharma
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    patient_story: Mapped[str] = mapped_column(Text, nullable=True)

    goal_usd: Mapped[float] = mapped_column(Float, nullable=False)
    raised_usd: Mapped[float] = mapped_column(Float, default=0.0)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Stripe Connect account ID for this patient's escrow
    stripe_account_id: Mapped[str] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="campaigns")
    result: Mapped["Result"] = relationship("Result", back_populates="campaign")
