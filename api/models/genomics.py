"""Multi-omic genomics models — Phase 1 clinical data model hardening.

Covers the data types beyond simple SNVs that cBioPortal supports:
  - CopyNumberAlteration  : gene-level CNA (log2 ratio, GISTIC, copy number)
  - StructuralVariant     : gene fusions and large SVs (DELLY / Manta output)
  - RnaSeqExpression      : per-gene TPM / FPKM / z-score from RNA-seq
  - MutationSignature     : COSMIC SBS signature decomposition weights

All models reference a Submission via submission_id so they integrate
seamlessly with the existing patient submission workflow.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ── Copy Number Alteration ─────────────────────────────────────────────────────

class CnaStatus(str, enum.Enum):
    """GISTIC-style discrete CNA call."""
    deep_deletion = "-2"       # Homozygous deletion
    shallow_deletion = "-1"    # Heterozygous deletion / loss
    diploid = "0"              # No change
    low_amplification = "1"    # Low-level gain
    high_amplification = "2"   # High-level amplification


class CopyNumberAlteration(Base):
    """Gene-level copy number alteration from CNVkit / GATK CNV pipeline."""
    __tablename__ = "copy_number_alterations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)

    gene: Mapped[str] = mapped_column(String(64), nullable=False)
    chromosome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    # Genomic coordinates of the CNV segment
    segment_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    segment_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Log2 ratio of tumour vs reference (CNVkit output)
    log2_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Estimated absolute copy number (rounded integer)
    copy_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Discrete GISTIC-style call: -2, -1, 0, 1, 2
    gistic_value: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    # CNA status enum derived from gistic_value
    cna_status: Mapped[Optional[CnaStatus]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    submission: Mapped["Submission"] = relationship("Submission", back_populates="copy_number_alterations")


# ── Structural Variant ─────────────────────────────────────────────────────────

class SvType(str, enum.Enum):
    fusion = "FUSION"
    deletion = "DELETION"
    duplication = "DUPLICATION"
    inversion = "INVERSION"
    translocation = "TRANSLOCATION"
    insertion = "INSERTION"
    unknown = "UNKNOWN"


class StructuralVariant(Base):
    """Gene fusion / large structural variant from DELLY or Manta."""
    __tablename__ = "structural_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)

    # For fusions: gene1 is the 5' partner, gene2 is the 3' partner
    gene1: Mapped[str] = mapped_column(String(64), nullable=False)
    gene2: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    chromosome1: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    breakpoint1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chromosome2: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    breakpoint2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    sv_type: Mapped[SvType] = mapped_column(String(20), default=SvType.unknown)

    # In-frame / out-of-frame fusion determination
    frame: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Supporting read count (paired + split reads from DELLY/Manta)
    support_reads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Is this SV clinically actionable (e.g. EML4-ALK → alectinib)
    is_actionable: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    submission: Mapped["Submission"] = relationship("Submission", back_populates="structural_variants")


# ── RNA-seq Expression ─────────────────────────────────────────────────────────

class RnaSeqExpression(Base):
    """Per-gene RNA-seq expression values from STAR + RSEM / featureCounts.

    Enables expression-informed drug ranking:
    e.g. high ERBB2 TPM → consider trastuzumab even without SNV.
    """
    __tablename__ = "rnaseq_expression"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)

    gene: Mapped[str] = mapped_column(String(64), nullable=False)
    # Transcripts Per Million — preferred unit for cross-sample comparison
    tpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Fragments Per Kilobase of exon per Million fragments mapped
    fpkm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # z-score relative to TCGA pan-cancer distribution for the same cancer type
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    submission: Mapped["Submission"] = relationship("Submission", back_populates="rnaseq_expression")


# ── Mutational Signature ───────────────────────────────────────────────────────

class MutationSignature(Base):
    """COSMIC SBS mutational signature decomposition (SigProfiler / deconstructSigs).

    Stores the top signatures detected in a tumour VCF:
      - SBS1  = age-related (clock-like)
      - SBS4  = tobacco smoking
      - SBS7a/b = UV radiation (melanoma)
      - SBS6/15/26 = defective mismatch repair (MSI)
      - SBS2/13 = APOBEC activity
    """
    __tablename__ = "mutation_signatures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)

    # COSMIC signature name (e.g. "SBS4", "SBS7a")
    signature_name: Mapped[str] = mapped_column(String(16), nullable=False)
    # Fractional weight of this signature (0–1); sum of top-N ≈ 1
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    # Human-readable aetiology (e.g. "Tobacco smoking")
    aetiology: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Rank among all detected signatures for this sample (1 = dominant)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    submission: Mapped["Submission"] = relationship("Submission", back_populates="mutation_signatures")
