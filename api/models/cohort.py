"""Multi-cohort / study browser data models — Phase 2.

cBioPortal's core value is multi-study genomic data exploration.  These models
power that capability in OpenOncology:

  Study         — a published or institutional genomic study (TCGA, ICGC, GEO…)
  Sample        — a single tumour sample belonging to a study
  CohortMutation — a somatic mutation observation within a public cohort sample
                   (separate from the patient-submitted Mutation table for privacy)

The ingestion pipeline (pipeline/ingest/) populates Study / Sample /
CohortMutation from public data sources.  The cohort query API
(routes/cohorts.py) exposes these for the study explorer and visualisations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Optional, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Study(Base):
    """A genomic study (TCGA cohort, ICGC project, institutional dataset, etc.)."""
    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Short machine-readable identifier, e.g. "tcga_luad_2016"
    study_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Primary cancer type (e.g. "LUAD", "BRCA") — cBioPortal cancer type ID
    cancer_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Human-readable cancer type label
    cancer_type_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    sample_count: Mapped[int] = mapped_column(Integer, default=0)

    # JSON array of data types present: ["SNV", "CNA", "RNA", "SV", "CLINICAL"]
    data_types: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Reference genome used for alignment (GRCh38, GRCh37, hg19, hg18)
    reference_genome: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # PubMed ID of the associated publication
    pmid: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Data source / repository (TCGA, ICGC, GEO, cBioPortal, institutional)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Whether this study is openly browsable without authentication
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    samples: Mapped[list["Sample"]] = relationship("Sample", back_populates="study")
    cohort_mutations: Mapped[list["CohortMutation"]] = relationship("CohortMutation", back_populates="study")


class Sample(Base):
    """A tumour sample belonging to a Study.

    For public cohort data (TCGA etc.) patient_id is NULL.
    For de-identified institutional cases it may reference a Patient record.
    """
    __tablename__ = "cohort_samples"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False)

    # Stable sample identifier within the source study
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # Patient identifier within the source study (de-identified)
    patient_sample_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Link to an OpenOncology Patient record only for institutional cases
    patient_id: Mapped[Optional[str]] = mapped_column(ForeignKey("patients.id"), nullable=True)

    tumor_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Tumour purity estimate (0–1) from ABSOLUTE or similar tool
    purity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Genome ploidy estimate
    ploidy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # MSI status: "MSI-H", "MSI-L", "MSS", or null
    msi_status: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    # Tumour mutational burden (mutations per Mb of exome)
    tmb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Overall survival data (months, event=1 deceased 0=censored)
    os_months: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    os_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Disease-free survival data
    dfs_months: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dfs_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    study: Mapped["Study"] = relationship("Study", back_populates="samples")
    cohort_mutations: Mapped[list["CohortMutation"]] = relationship("CohortMutation", back_populates="sample")


class CohortMutation(Base):
    """A somatic mutation observation in a public cohort sample.

    Kept separate from the patient-facing Mutation table to avoid any
    possible cross-contamination of PHI with public research data.
    """
    __tablename__ = "cohort_mutations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False)
    sample_id: Mapped[str] = mapped_column(ForeignKey("cohort_samples.id"), nullable=False)

    gene: Mapped[str] = mapped_column(String(64), nullable=False)
    # Protein change in standard notation (e.g. p.L858R, p.G12D)
    protein_change: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # HGVS coding sequence change
    hgvs_c: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # MAF variant classification (Missense_Mutation, Frame_Shift_Del, etc.)
    variant_classification: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Chromosome and position in the source reference genome
    chromosome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ref_allele: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    alt_allele: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Variant allele frequency
    vaf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # OncoKB actionability level for this gene + alteration combination
    oncokb_level: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    study: Mapped["Study"] = relationship("Study", back_populates="cohort_mutations")
    sample: Mapped["Sample"] = relationship("Sample", back_populates="cohort_mutations")
