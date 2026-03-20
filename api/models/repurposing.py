import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RepurposingCandidate(Base):
    __tablename__ = "repurposing"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    result_id: Mapped[str] = mapped_column(ForeignKey("results.id"), nullable=False)

    drug_name: Mapped[str] = mapped_column(String(256), nullable=False)
    chembl_id: Mapped[str] = mapped_column(String(64), nullable=True)

    # DiffDock binding affinity score (lower = stronger binding)
    binding_score: Mapped[float] = mapped_column(Float, nullable=True)

    # OpenTargets association score (0–1)
    opentargets_score: Mapped[float] = mapped_column(Float, nullable=True)

    # Combined rank score — weighted combination of both
    rank_score: Mapped[float] = mapped_column(Float, nullable=True)

    # FDA / EMA approval status from ChEMBL
    approval_status: Mapped[str] = mapped_column(String(128), nullable=True)

    # Mechanism of action
    mechanism: Mapped[str] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    result: Mapped["Result"] = relationship("Result", back_populates="repurposing_candidates")
