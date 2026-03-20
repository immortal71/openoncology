import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Store hashed email — never plaintext
    email_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=True)
    keycloak_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    # Consent
    consent_research_sharing: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    # GDPR: delete after this many days (0 = keep indefinitely with consent)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=365)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="patient")
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="patient")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="patient")
