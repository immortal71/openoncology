import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any

from database import Base


class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id"), unique=True, nullable=False
    )

    has_targetable_mutation: Mapped[bool] = mapped_column(Boolean, default=False)
    target_gene: Mapped[str] = mapped_column(String(64), nullable=True)

    # Technical summary for clinician review
    summary_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Plain-language LLM-generated explanation for the patient
    plain_language_summary: Mapped[str] = mapped_column(Text, nullable=True)

    # cBioPortal cohort frequency data (JSON array of {study_id, cancer_type, mutation_count})
    cbioportal_data: Mapped[Any] = mapped_column(JSON, nullable=True)

    # COSMIC sample count for the primary mutated gene
    cosmic_sample_count: Mapped[int] = mapped_column(String(32), nullable=True)

    # S3 key for the generated PDF report
    report_pdf_s3_key: Mapped[str] = mapped_column(String(512), nullable=True)

    # Oncologist review
    oncologist_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    oncologist_id: Mapped[str] = mapped_column(ForeignKey("oncologists.id"), nullable=True)
    oncologist_notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped["Submission"] = relationship("Submission", back_populates="result")
    repurposing_candidates: Mapped[list["RepurposingCandidate"]] = relationship(
        "RepurposingCandidate", back_populates="result"
    )
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="result", uselist=False)
