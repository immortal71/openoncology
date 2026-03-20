import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Oncologist(Base):
    __tablename__ = "oncologists"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    keycloak_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    specialty: Mapped[str] = mapped_column(String(128), nullable=True)
    institution: Mapped[str] = mapped_column(String(256), nullable=True)

    # Verified by platform admin
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reports_reviewed: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
