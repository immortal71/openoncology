import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class MutationClassification(str, enum.Enum):
    pathogenic = "pathogenic"
    likely_pathogenic = "likely_pathogenic"
    uncertain = "uncertain"
    likely_benign = "likely_benign"
    benign = "benign"


class OncoKBLevel(str, enum.Enum):
    level_1 = "1"    # FDA-approved biomarker
    level_2 = "2"    # Standard care biomarker
    level_3a = "3A"  # Compelling clinical evidence
    level_3b = "3B"  # Standard care in other cancer type
    level_4 = "4"    # Compelling biological evidence
    r1 = "R1"        # Standard care resistance
    r2 = "R2"        # Resistance
    unknown = "unknown"


class Mutation(Base):
    __tablename__ = "mutations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)

    gene: Mapped[str] = mapped_column(String(64), nullable=False)
    hgvs_notation: Mapped[str] = mapped_column(String(256), nullable=True)
    mutation_type: Mapped[str] = mapped_column(String(64), nullable=True)  # e.g. missense, frameshift
    chromosome: Mapped[str] = mapped_column(String(8), nullable=True)
    position: Mapped[int] = mapped_column(nullable=True)
    ref_allele: Mapped[str] = mapped_column(String(64), nullable=True)
    alt_allele: Mapped[str] = mapped_column(String(64), nullable=True)

    # Classification from AlphaMissense
    classification: Mapped[MutationClassification] = mapped_column(
        SAEnum(MutationClassification), default=MutationClassification.uncertain
    )
    alphamissense_score: Mapped[float] = mapped_column(Float, nullable=True)

    # OncoKB actionability level
    oncokb_level: Mapped[OncoKBLevel] = mapped_column(
        SAEnum(OncoKBLevel), default=OncoKBLevel.unknown
    )

    # ClinVar / COSMIC IDs for reference
    clinvar_id: Mapped[str] = mapped_column(String(64), nullable=True)
    cosmic_id: Mapped[str] = mapped_column(String(64), nullable=True)

    is_targetable: Mapped[bool] = mapped_column(default=False)

    # AlphaFold Server — path in MinIO after mutation-specific folding
    alphafold_structure_path: Mapped[str] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped["Submission"] = relationship("Submission", back_populates="mutations")
