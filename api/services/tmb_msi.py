"""Tumour Mutational Burden (TMB) and Microsatellite Instability (MSI) scoring.

TMB
---
TMB is defined as the number of somatic, coding, non-synonymous mutations per
megabase of exome sequenced.  It is a predictive biomarker for immune checkpoint
inhibitor response (pembrolizumab: FDA-approved for TMB-High ≥10 mut/Mb,
June 2020, KEYNOTE-158).

Classification thresholds (ESMO / FDA guidance):
  - TMB-High   : ≥ 10 mutations per Mb
  - TMB-Low    :  < 10 mutations per Mb

MSI
---
MSI is detected by counting frameshift insertions/deletions (indels) in known
microsatellite repeat tracts.  High MSI (MSI-H) is a pan-tumour biomarker for
pembrolizumab (FDA-approved 2017, KEYNOTE-016/158).

Classification thresholds:
  - MSI-H  : ≥ 20% of loci show instability  (or frameshift fraction ≥ 0.15)
  - MSS    : < 5%  of loci show instability
  - MSI-L  : 5–20% (indeterminate)

References:
  - Yarchoan et al., NEJM 2017 — TMB and immunotherapy
  - Le et al., Science 2017  — MSI-H and pembrolizumab
  - Merino et al., JCO 2020  — standardising TMB thresholds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# ESMO / FDA TMB-High threshold (mutations per Mb of exome)
TMB_HIGH_THRESHOLD = 10.0
# Approximate size of the human exome coding region in megabases
EXOME_SIZE_MB = 33.0

# Non-synonymous MAF variant classifications used for TMB counting
NONSYNONYMOUS_CLASSIFICATIONS = {
    "Missense_Mutation",
    "Nonsense_Mutation",
    "Frame_Shift_Del",
    "Frame_Shift_Ins",
    "Splice_Site",
    "Translation_Start_Site",
    "Nonstop_Mutation",
    "De_novo_Start_InFrame",
    "De_novo_Start_OutOfFrame",
    "In_Frame_Del",
    "In_Frame_Ins",
}

# MSI thresholds based on frameshift indel fraction
MSI_HIGH_FRACTION = 0.15   # ≥15% of mutations are frameshift indels → MSI-H
MSI_LOW_FRACTION = 0.05    # <5% → MSS; 5–15% → MSI-L

# Frame-shift variant classifications
FRAMESHIFT_CLASSIFICATIONS = {"Frame_Shift_Del", "Frame_Shift_Ins"}


# ── Result dataclasses ─────────────────────────────────────────────────────────

@dataclass
class TmbResult:
    """Tumour Mutational Burden calculation result."""
    nonsynonymous_count: int
    exome_size_mb: float
    tmb_per_mb: float
    classification: str        # "TMB-High" or "TMB-Low"
    confidence: str            # "HIGH" (>30 coding muts), "MEDIUM" (10–30), "LOW" (<10)
    note: str


@dataclass
class MsiResult:
    """Microsatellite Instability classification result."""
    total_mutations: int
    frameshift_count: int
    frameshift_fraction: float
    classification: str        # "MSI-H", "MSI-L", "MSS"
    note: str


@dataclass
class TmbMsiReport:
    """Combined TMB + MSI report for a patient submission."""
    tmb: TmbResult
    msi: MsiResult
    immunotherapy_relevant: bool
    immunotherapy_note: str


# ── TMB calculation ────────────────────────────────────────────────────────────

def calculate_tmb(
    mutations: list[dict],
    exome_size_mb: float = EXOME_SIZE_MB,
) -> TmbResult:
    """Calculate TMB from a list of mutation dicts.

    Args:
        mutations: list of mutation dicts, each with a ``variant_classification``
                   key.  Can be from the DB ORM or from a VCF parse step.
        exome_size_mb: Effective coding region size (default 33 Mb for WES).
                       Use ~2.5 Mb for targeted panels (and note reduced accuracy).

    Returns:
        TmbResult with classification and clinical note.
    """
    if not mutations:
        return TmbResult(
            nonsynonymous_count=0,
            exome_size_mb=exome_size_mb,
            tmb_per_mb=0.0,
            classification="TMB-Low",
            confidence="LOW",
            note="No mutations available for TMB calculation.",
        )

    nonsynonymous = [
        m for m in mutations
        if (m.get("variant_classification") or m.get("mutation_type", "")) in NONSYNONYMOUS_CLASSIFICATIONS
    ]
    n = len(nonsynonymous)
    tmb_per_mb = round(n / exome_size_mb, 2)
    classification = "TMB-High" if tmb_per_mb >= TMB_HIGH_THRESHOLD else "TMB-Low"

    if n >= 30:
        confidence = "HIGH"
    elif n >= 10:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if classification == "TMB-High":
        note = (
            f"TMB-High ({tmb_per_mb:.1f} mut/Mb ≥ {TMB_HIGH_THRESHOLD} threshold). "
            "FDA-approved pembrolizumab eligibility should be discussed with oncologist "
            "(KEYNOTE-158; approved June 2020 for solid tumours)."
        )
    else:
        note = (
            f"TMB-Low ({tmb_per_mb:.1f} mut/Mb < {TMB_HIGH_THRESHOLD} threshold). "
            "Immune checkpoint inhibitor benefit is less likely from TMB alone; "
            "PD-L1 expression and MSI status should also be assessed."
        )

    logger.debug("[tmb] count=%d exome=%.1fMb tmb=%.2f class=%s", n, exome_size_mb, tmb_per_mb, classification)
    return TmbResult(
        nonsynonymous_count=n,
        exome_size_mb=exome_size_mb,
        tmb_per_mb=tmb_per_mb,
        classification=classification,
        confidence=confidence,
        note=note,
    )


# ── MSI calculation ────────────────────────────────────────────────────────────

def calculate_msi(mutations: list[dict]) -> MsiResult:
    """Estimate MSI status from frameshift indel fraction in the mutation list.

    This is a VCF-based proxy for MSI (analogous to MSIsensor).  A high
    fraction of frameshift mutations relative to all mutations is a hallmark
    of defective DNA mismatch repair (dMMR), the molecular basis of MSI-H.

    For a robust MSI call in production, use MSIsensor2 or MANTIS on the BAM
    and store the result directly.  This function provides a quick screen from
    the VCF alone.
    """
    total = len(mutations)
    if total == 0:
        return MsiResult(
            total_mutations=0,
            frameshift_count=0,
            frameshift_fraction=0.0,
            classification="MSS",
            note="Insufficient mutations for MSI estimation.",
        )

    frameshifts = [
        m for m in mutations
        if (m.get("variant_classification") or m.get("mutation_type", "")) in FRAMESHIFT_CLASSIFICATIONS
    ]
    fs_count = len(frameshifts)
    fs_fraction = round(fs_count / total, 4) if total > 0 else 0.0

    if fs_fraction >= MSI_HIGH_FRACTION:
        classification = "MSI-H"
        note = (
            f"MSI-High signal detected (frameshift fraction={fs_fraction:.1%} ≥ "
            f"{MSI_HIGH_FRACTION:.0%}). "
            "Pan-tumour FDA approval for pembrolizumab (Le et al., Science 2017). "
            "Recommend confirmatory MSIsensor2 assay on tumour BAM."
        )
    elif fs_fraction >= MSI_LOW_FRACTION:
        classification = "MSI-L"
        note = (
            f"MSI-Low / indeterminate (frameshift fraction={fs_fraction:.1%}). "
            "Recommend MSIsensor2 on tumour BAM for a definitive call."
        )
    else:
        classification = "MSS"
        note = (
            f"Microsatellite Stable (frameshift fraction={fs_fraction:.1%} < "
            f"{MSI_LOW_FRACTION:.0%}). "
            "Immune checkpoint inhibitor benefit from MSI-H pathway is unlikely."
        )

    logger.debug("[msi] total=%d frameshifts=%d fraction=%.4f class=%s", total, fs_count, fs_fraction, classification)
    return MsiResult(
        total_mutations=total,
        frameshift_count=fs_count,
        frameshift_fraction=fs_fraction,
        classification=classification,
        note=note,
    )


# ── Combined report ────────────────────────────────────────────────────────────

def run_tmb_msi_analysis(
    mutations: list[dict],
    exome_size_mb: float = EXOME_SIZE_MB,
) -> TmbMsiReport:
    """Run both TMB and MSI analysis and return a combined report.

    Args:
        mutations: list of mutation dicts with at least ``variant_classification``
                   (or ``mutation_type``) keys.
        exome_size_mb: Exome / panel size in megabases.

    Returns:
        TmbMsiReport with TMB result, MSI result, and immunotherapy relevance flag.
    """
    tmb = calculate_tmb(mutations, exome_size_mb)
    msi = calculate_msi(mutations)

    immunotherapy_relevant = (
        tmb.classification == "TMB-High" or msi.classification == "MSI-H"
    )

    if tmb.classification == "TMB-High" and msi.classification == "MSI-H":
        io_note = (
            "Both TMB-High and MSI-H detected. Strong immunotherapy signal. "
            "Pembrolizumab should be discussed with oncologist for both biomarkers."
        )
    elif msi.classification == "MSI-H":
        io_note = (
            "MSI-High detected. FDA pan-tumour approval for pembrolizumab. "
            "TMB is below the 10 mut/Mb threshold but MSI-H alone is an approved indication."
        )
    elif tmb.classification == "TMB-High":
        io_note = (
            "TMB-High detected. FDA approval for pembrolizumab in solid tumours with "
            "TMB ≥10 mut/Mb (KEYNOTE-158). Microsatellite status appears stable."
        )
    else:
        io_note = (
            "Neither TMB-High nor MSI-H detected. Immunotherapy eligibility should "
            "be evaluated on other biomarkers (PD-L1, tumour type-specific criteria)."
        )

    return TmbMsiReport(
        tmb=tmb,
        msi=msi,
        immunotherapy_relevant=immunotherapy_relevant,
        immunotherapy_note=io_note,
    )


def tmb_msi_to_dict(report: TmbMsiReport) -> dict:
    """Serialise TmbMsiReport to a JSON-safe dict for API responses."""
    return {
        "tmb": {
            "nonsynonymous_count": report.tmb.nonsynonymous_count,
            "exome_size_mb": report.tmb.exome_size_mb,
            "tmb_per_mb": report.tmb.tmb_per_mb,
            "classification": report.tmb.classification,
            "confidence": report.tmb.confidence,
            "note": report.tmb.note,
        },
        "msi": {
            "total_mutations": report.msi.total_mutations,
            "frameshift_count": report.msi.frameshift_count,
            "frameshift_fraction": report.msi.frameshift_fraction,
            "classification": report.msi.classification,
            "note": report.msi.note,
        },
        "immunotherapy_relevant": report.immunotherapy_relevant,
        "immunotherapy_note": report.immunotherapy_note,
    }
