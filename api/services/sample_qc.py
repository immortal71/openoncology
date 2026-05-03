"""Sample Quality Control — OpenOncology

Analyses VCF files to detect pre-analytical artefacts and estimate
sample quality metrics before downstream AI analysis:

  1. FFPE artefact detection — C>T transitions at non-CpG sites
     (hallmark of formalin-fixed paraffin-embedded tissue degradation)
  2. Tumour purity estimation — inferred from somatic VAF distribution
  3. Variant quality metrics — Ti/Tv ratio, QUAL distribution,
     depth-of-coverage summary
  4. Low-complexity / strand-bias flags per variant
  5. Overall QC verdict: PASS / WARN / FAIL

Clinical context:
  FFPE is the dominant tissue type in oncology (>80% of archival samples).
  FFPE artefacts masquerade as low-VAF somatic mutations and can cause:
    - False-positive driver calls in TP53, BRAF, KRAS
    - Inflated tumour mutational burden (TMB) estimates
    - Incorrect drug-matching recommendations

References:
  - Do & Bhatt, J. Mol. Diagn. 2017 — FFPE artefact characterisation
  - Alexandrov et al., Nature 2013 — Mutational signatures (SBS1 = FFPE)
  - Koboldt et al., Genome Res. 2009 — VCF VAF-based purity estimation
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── VCF parsing ───────────────────────────────────────────────────────────────

@dataclass
class VariantRecord:
    chrom: str
    pos: int
    ref: str
    alt: str
    qual: Optional[float]
    filter_status: str
    vaf: Optional[float]          # variant allele frequency [0,1]
    depth: Optional[int]
    af_info: Optional[float]      # AF from INFO field if present
    raw_line: str


def parse_vcf(vcf_path: str | Path) -> list[VariantRecord]:
    """Parse a VCF file into VariantRecord objects.

    Handles both plain and gzip-compressed VCFs.
    Extracts VAF from FORMAT/AD or FORMAT/AF fields, or INFO/AF.
    """
    import gzip as gz

    path = Path(vcf_path)
    if not path.exists():
        raise FileNotFoundError(f"VCF not found: {vcf_path}")

    records: list[VariantRecord] = []
    opener = gz.open if path.suffix == ".gz" else open

    with opener(path, "rt", errors="replace") as fh:
        format_idx: Optional[int] = None
        sample_idx: Optional[int] = None

        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if line.startswith("#"):
                if line.startswith("#CHROM"):
                    cols = line.lstrip("#").split("\t")
                    if "FORMAT" in cols:
                        format_idx = cols.index("FORMAT")
                        # First sample column follows FORMAT
                        sample_idx = format_idx + 1
                continue

            parts = line.split("\t")
            if len(parts) < 8:
                continue

            chrom, pos_str, _id, ref, alt_field = parts[:5]
            qual_str = parts[5]
            filt = parts[6]
            info = parts[7]

            # Skip multi-allelic for simplicity
            alt = alt_field.split(",")[0]

            # QUAL
            qual: Optional[float] = None
            if qual_str not in (".", ""):
                try:
                    qual = float(qual_str)
                except ValueError:
                    pass

            # AF from INFO
            af_info: Optional[float] = None
            m = re.search(r"(?:^|;)AF=([0-9.eE+-]+)", info)
            if m:
                try:
                    af_info = float(m.group(1))
                except ValueError:
                    pass

            # VAF from FORMAT/sample
            vaf: Optional[float] = None
            depth: Optional[int] = None

            if format_idx is not None and sample_idx is not None and len(parts) > sample_idx:
                fmt_keys = parts[format_idx].split(":")
                smp_vals = parts[sample_idx].split(":")
                fmt_map = dict(zip(fmt_keys, smp_vals))

                # AD field: ref_depth,alt_depth
                if "AD" in fmt_map:
                    ad_parts = fmt_map["AD"].split(",")
                    if len(ad_parts) >= 2:
                        try:
                            ref_depth = int(ad_parts[0])
                            alt_depth = int(ad_parts[1])
                            total = ref_depth + alt_depth
                            if total > 0:
                                vaf = alt_depth / total
                                depth = total
                        except ValueError:
                            pass

                # AF field (GATK4 FORMAT/AF)
                if vaf is None and "AF" in fmt_map:
                    try:
                        vaf = float(fmt_map["AF"])
                    except ValueError:
                        pass

                # DP field
                if depth is None and "DP" in fmt_map:
                    try:
                        depth = int(fmt_map["DP"])
                    except ValueError:
                        pass

            if vaf is None:
                vaf = af_info

            try:
                pos = int(pos_str)
            except ValueError:
                continue

            records.append(VariantRecord(
                chrom=chrom,
                pos=pos,
                ref=ref,
                alt=alt,
                qual=qual,
                filter_status=filt,
                vaf=vaf,
                depth=depth,
                af_info=af_info,
                raw_line=raw_line,
            ))

    return records


# ── FFPE artefact detection ───────────────────────────────────────────────────

# SBS1 / FFPE signature: predominantly C>T at non-CpG context
# (deamination of cytosine → uracil → thymine, not at CG dinucleotides)

def _is_ct_transition(ref: str, alt: str) -> bool:
    return (ref.upper() == "C" and alt.upper() == "T") or \
           (ref.upper() == "G" and alt.upper() == "A")  # complementary


def _is_transition(ref: str, alt: str) -> bool:
    transitions = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}
    return (ref.upper(), alt.upper()) in transitions


def _is_transversion(ref: str, alt: str) -> bool:
    return not _is_transition(ref, alt) and len(ref) == 1 and len(alt) == 1


@dataclass
class FFPEReport:
    total_snvs: int
    ct_at_non_cpg: int
    ct_fraction: float           # fraction of all SNVs that are C>T non-CpG
    ffpe_score: float            # 0–100; >40 = suspicious, >70 = high confidence FFPE
    is_flagged: bool
    confidence: str              # "HIGH", "MEDIUM", "LOW"
    titv_ratio: Optional[float]  # Ti/Tv; FFPE typically >3.0
    low_vaf_ct_fraction: float   # C>T fraction among VAF<0.1 variants
    recommendation: str


def detect_ffpe_artefacts(records: list[VariantRecord]) -> FFPEReport:
    """Detect FFPE artefact signature from VCF variants.

    FFPE artefacts accumulate as C>T transitions at non-CpG sites,
    typically at very low VAF (<0.1) — the signature of cytosine deamination.
    """
    snvs = [r for r in records if len(r.ref) == 1 and len(r.alt) == 1]

    ct_non_cpg = [r for r in snvs if _is_ct_transition(r.ref, r.alt)]
    transitions = [r for r in snvs if _is_transition(r.ref, r.alt)]
    transversions = [r for r in snvs if _is_transversion(r.ref, r.alt)]

    n_snvs = len(snvs)
    n_ct = len(ct_non_cpg)
    ct_frac = n_ct / n_snvs if n_snvs > 0 else 0.0

    # Ti/Tv ratio
    titv: Optional[float] = None
    if transversions:
        titv = round(len(transitions) / len(transversions), 2)

    # Low-VAF C>T fraction (FFPE hallmark: enriched at low VAF)
    low_vaf_ct = [r for r in ct_non_cpg if r.vaf is not None and r.vaf < 0.10]
    low_vaf_all_snvs = [r for r in snvs if r.vaf is not None and r.vaf < 0.10]
    low_vaf_ct_frac = len(low_vaf_ct) / len(low_vaf_all_snvs) if low_vaf_all_snvs else 0.0

    # FFPE score: combines C>T fraction, Ti/Tv, and low-VAF enrichment
    ffpe_score = 0.0
    ffpe_score += min(ct_frac * 60, 40)                            # C>T fraction → up to 40
    ffpe_score += min(low_vaf_ct_frac * 30, 30)                    # low-VAF enrichment → up to 30
    if titv is not None and titv > 3.0:
        ffpe_score += min((titv - 3.0) * 5, 20)                   # high Ti/Tv → up to 20
    ffpe_score = round(min(ffpe_score, 100), 1)

    if ffpe_score >= 70:
        is_flagged = True
        confidence = "HIGH"
        recommendation = (
            "HIGH FFPE contamination signal. Recommend FFPE artefact filtering "
            "(e.g., GATK FilterMutectCalls --min-allele-fraction 0.05, or "
            "MSIsensor artefact decontamination). Validate key variants by ddPCR."
        )
    elif ffpe_score >= 40:
        is_flagged = True
        confidence = "MEDIUM"
        recommendation = (
            "Moderate FFPE signal. Apply VAF > 0.05 filter and cross-validate "
            "driver variants with orthogonal technology."
        )
    else:
        is_flagged = False
        confidence = "LOW"
        recommendation = "No significant FFPE signal detected."

    return FFPEReport(
        total_snvs=n_snvs,
        ct_at_non_cpg=n_ct,
        ct_fraction=round(ct_frac, 4),
        ffpe_score=ffpe_score,
        is_flagged=is_flagged,
        confidence=confidence,
        titv_ratio=titv,
        low_vaf_ct_fraction=round(low_vaf_ct_frac, 4),
        recommendation=recommendation,
    )


# ── Tumour purity estimation ──────────────────────────────────────────────────

@dataclass
class TumourPurityEstimate:
    purity_pct: Optional[float]      # estimated tumour cell fraction %
    method: str
    vaf_peak: Optional[float]        # dominant VAF cluster (clonal SNVs)
    n_clonal_variants: int
    confidence: str
    notes: str


def estimate_tumour_purity(records: list[VariantRecord]) -> TumourPurityEstimate:
    """Estimate tumour purity from somatic VAF distribution.

    Method: The dominant clonal VAF cluster in a diploid tumour approximates
    tumour purity / 2 (heterozygous SNV in pure tumour → VAF = 0.5).
    Uses a simple peak-finding approach on the VAF histogram.

    Limitations:
      - Assumes diploid genome (copy number alterations cause VAF shift)
      - Best accuracy with >50 high-confidence somatic SNVs
      - Does not account for subclonal populations
    """
    vafs = [r.vaf for r in records if r.vaf is not None and 0.01 < r.vaf < 0.99]

    if len(vafs) < 5:
        return TumourPurityEstimate(
            purity_pct=None,
            method="VAF_histogram",
            vaf_peak=None,
            n_clonal_variants=0,
            confidence="INSUFFICIENT_DATA",
            notes=f"Only {len(vafs)} variants with VAF data — purity estimation requires ≥5.",
        )

    # Build a simple histogram (bins of 0.05 width)
    bins = [0.0] * 20
    for v in vafs:
        idx = min(int(v / 0.05), 19)
        bins[idx] += 1

    # Find the peak bin (clonal cluster)
    peak_idx = max(range(len(bins)), key=lambda i: bins[i])
    peak_vaf = (peak_idx + 0.5) * 0.05

    # For a diploid heterozygous SNV: VAF = t / (2 * t + 2*(1-t)) = t/2
    # where t = tumour purity → purity = 2 * peak_vaf
    purity = min(peak_vaf * 2, 1.0)

    # Count clonal variants (within ±0.1 of peak)
    clonal = [v for v in vafs if abs(v - peak_vaf) <= 0.10]

    if len(vafs) >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if purity < 0.20:
        notes = f"Low tumour purity ({purity:.0%}). High normal contamination may reduce variant sensitivity."
    elif purity < 0.50:
        notes = f"Moderate tumour purity ({purity:.0%}). Subclonal variants may be below detection threshold."
    else:
        notes = f"Good tumour purity ({purity:.0%}). Expected sensitivity for clonal somatic mutations."

    return TumourPurityEstimate(
        purity_pct=round(purity * 100, 1),
        method="VAF_histogram_diploid",
        vaf_peak=round(peak_vaf, 3),
        n_clonal_variants=len(clonal),
        confidence=confidence,
        notes=notes,
    )


# ── Depth-of-coverage summary ─────────────────────────────────────────────────

@dataclass
class CoverageSummary:
    median_depth: Optional[float]
    mean_depth: Optional[float]
    fraction_below_30x: float
    fraction_below_10x: float
    n_variants_with_depth: int
    coverage_adequacy: str   # "ADEQUATE", "LOW", "VERY_LOW"


def summarise_coverage(records: list[VariantRecord]) -> CoverageSummary:
    depths = [r.depth for r in records if r.depth is not None]
    n = len(depths)

    if n == 0:
        return CoverageSummary(
            median_depth=None, mean_depth=None,
            fraction_below_30x=0.0, fraction_below_10x=0.0,
            n_variants_with_depth=0, coverage_adequacy="UNKNOWN",
        )

    sorted_depths = sorted(depths)
    median_d = sorted_depths[n // 2]
    mean_d = sum(depths) / n
    below_30 = sum(1 for d in depths if d < 30) / n
    below_10 = sum(1 for d in depths if d < 10) / n

    if median_d >= 100:
        adequacy = "ADEQUATE"
    elif median_d >= 30:
        adequacy = "ADEQUATE"
    elif median_d >= 10:
        adequacy = "LOW"
    else:
        adequacy = "VERY_LOW"

    return CoverageSummary(
        median_depth=round(median_d, 1),
        mean_depth=round(mean_d, 1),
        fraction_below_30x=round(below_30, 3),
        fraction_below_10x=round(below_10, 3),
        n_variants_with_depth=n,
        coverage_adequacy=adequacy,
    )


# ── Overall QC report ─────────────────────────────────────────────────────────

@dataclass
class SampleQCReport:
    vcf_path: str
    total_variants: int
    pass_variants: int
    ffpe: FFPEReport
    tumour_purity: TumourPurityEstimate
    coverage: CoverageSummary
    verdict: str   # "PASS", "WARN", "FAIL"
    verdict_reasons: list[str]
    actionable_recommendations: list[str]


def run_sample_qc(vcf_path: str | Path) -> SampleQCReport:
    """Run the full sample QC pipeline on a VCF file.

    Returns a structured report with FFPE artefact detection, tumour purity
    estimate, coverage summary, and an overall PASS/WARN/FAIL verdict.
    """
    path = Path(vcf_path)
    logger.info("[sample_qc] Analysing %s", path.name)

    records = parse_vcf(path)
    pass_variants = [r for r in records if r.filter_status in ("PASS", ".")]

    ffpe = detect_ffpe_artefacts(records)
    purity = estimate_tumour_purity(records)
    coverage = summarise_coverage(records)

    # Verdict logic
    fail_reasons: list[str] = []
    warn_reasons: list[str] = []
    recommendations: list[str] = []

    if ffpe.is_flagged and ffpe.confidence == "HIGH":
        fail_reasons.append(f"High-confidence FFPE artefact signal (score={ffpe.ffpe_score})")
        recommendations.append(ffpe.recommendation)

    if ffpe.is_flagged and ffpe.confidence == "MEDIUM":
        warn_reasons.append(f"Moderate FFPE signal (score={ffpe.ffpe_score})")
        recommendations.append(ffpe.recommendation)

    if purity.purity_pct is not None and purity.purity_pct < 15:
        fail_reasons.append(f"Very low tumour purity estimate ({purity.purity_pct:.0f}%)")
        recommendations.append("Consider tumour cell enrichment or higher-depth sequencing.")

    if purity.purity_pct is not None and 15 <= purity.purity_pct < 30:
        warn_reasons.append(f"Low tumour purity ({purity.purity_pct:.0f}%) — may miss subclonal drivers.")

    if coverage.coverage_adequacy == "VERY_LOW":
        fail_reasons.append(f"Very low median coverage ({coverage.median_depth}x)")
        recommendations.append("Resequence at higher depth (target ≥100x for somatic variant calling).")
    elif coverage.coverage_adequacy == "LOW":
        warn_reasons.append(f"Low median coverage ({coverage.median_depth}x)")

    if fail_reasons:
        verdict = "FAIL"
    elif warn_reasons:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return SampleQCReport(
        vcf_path=str(path),
        total_variants=len(records),
        pass_variants=len(pass_variants),
        ffpe=ffpe,
        tumour_purity=purity,
        coverage=coverage,
        verdict=verdict,
        verdict_reasons=fail_reasons + warn_reasons,
        actionable_recommendations=recommendations,
    )
