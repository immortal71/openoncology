import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class SubmissionStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    awaiting_ai = "awaiting_ai"
    complete = "complete"
    failed = "failed"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    cancer_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus), default=SubmissionStatus.queued
    )

    # S3/MinIO keys — never expose to client
    biopsy_s3_key: Mapped[str] = mapped_column(String(512), nullable=True)
    dna_s3_key: Mapped[str] = mapped_column(String(512), nullable=True)
    vcf_s3_key: Mapped[str] = mapped_column(String(512), nullable=True)

    # Celery job IDs for tracking
    pipeline_job_id: Mapped[str] = mapped_column(String(128), nullable=True)
    ai_job_id: Mapped[str] = mapped_column(String(128), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="submissions")
    mutations: Mapped[list["Mutation"]] = relationship("Mutation", back_populates="submission")
    result: Mapped["Result"] = relationship("Result", back_populates="submission", uselist=False)
