import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Float, Enum as SAEnum, Integer, Boolean
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


# MAF variant_classification values (Broad / cBioPortal standard)
MAF_VARIANT_CLASSIFICATIONS = (
    "Missense_Mutation", "Nonsense_Mutation", "Frame_Shift_Del",
    "Frame_Shift_Ins", "Splice_Site", "Splice_Region", "In_Frame_Del",
    "In_Frame_Ins", "Silent", "3'UTR", "5'UTR", "Intron",
    "RNA", "Translation_Start_Site", "Nonstop_Mutation",
    "De_novo_Start_InFrame", "De_novo_Start_OutOfFrame",
    "Targeted_Region", "IGR",
)


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

    # ── Full MAF-spec fields ────────────────────────────────────────────────────
    # Variant allele frequency (0–1) computed from AD or AF FORMAT fields
    vaf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Total read depth at the variant position
    depth: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Reference and alternate allele read depths (from AD FORMAT field)
    allele_depth_ref: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allele_depth_alt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Strand bias — SB or FS PHRED score from GATK INFO field
    strand_bias: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # MAF variant classification (Missense_Mutation, Frame_Shift_Del, etc.)
    variant_classification: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # RefSeq transcript identifier (e.g. NM_004333.6)
    refseq_transcript_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Amino-acid position of the change (integer, e.g. 858 for L858R)
    protein_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Codon change string (e.g. c.2573T>G)
    codon_change: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Cancer Hotspots v2 flag — True when this residue is a recurrent hotspot
    hotspot_flag: Mapped[bool] = mapped_column(Boolean, default=False)

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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    submission: Mapped["Submission"] = relationship("Submission", back_populates="mutations")
