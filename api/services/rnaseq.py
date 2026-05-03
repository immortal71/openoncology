"""RNA-seq & Multi-omics Integration Service — OpenOncology

Integrates transcriptomic and additional omics layers with the primary
DNA-based analysis to improve drug repurposing accuracy:

  1. Gene expression integration — identifies over/under-expressed drug targets
     from RNA-seq differential expression data (DESeq2 / edgeR output format).
  2. Fusion gene detection — parses STAR-Fusion / Arriba output to identify
     actionable fusion drivers (ALK, RET, ROS1, NTRK, FGFR, etc.).
  3. Expression-guided drug repurposing — re-weights drug candidates based on
     target expression level (overexpressed targets = higher drug priority).
  4. Tumour microenvironment (TME) — reads TIMER2 / CIBERSORT deconvolution
     output to characterise immune infiltration (relevant for immunotherapy).
  5. Methylation annotation — parses CpG methylation data to identify
     silenced tumour suppressors.

Data formats supported:
  - DESeq2 / edgeR TSV: columns gene_id, log2FoldChange, padj
  - STAR-Fusion: FusionName, JunctionReadCount, SpanningFragCount columns
  - Arriba: gene1, gene2, confidence, breakpoint columns
  - TIMER2 JSON export or CIBERSORT TXT

Note: RNA-seq data integration is additive — all DNA-based results remain
valid when RNA data is absent. This module adds optional expression weights.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Known actionable fusion partners ─────────────────────────────────────────
# Gene → approved/clinical-stage drug(s)
ACTIONABLE_FUSIONS: dict[str, list[str]] = {
    "ALK": ["Alectinib", "Crizotinib", "Brigatinib", "Lorlatinib", "Ceritinib"],
    "RET": ["Selpercatinib", "Pralsetinib"],
    "ROS1": ["Crizotinib", "Entrectinib", "Lorlatinib"],
    "NTRK1": ["Larotrectinib", "Entrectinib"],
    "NTRK2": ["Larotrectinib", "Entrectinib"],
    "NTRK3": ["Larotrectinib", "Entrectinib"],
    "FGFR1": ["Pemigatinib", "Erdafitinib"],
    "FGFR2": ["Pemigatinib", "Futibatinib", "Infigratinib"],
    "FGFR3": ["Erdafitinib"],
    "MET": ["Capmatinib", "Tepotinib", "Crizotinib"],
    "PDGFRA": ["Avapritinib", "Imatinib"],
    "NRG1": ["Seribantumab", "Afatinib"],
    "EWSR1": ["Olaratumab"],
    "BCR": ["Imatinib", "Dasatinib", "Nilotinib", "Ponatinib"],
}


# ── Gene expression integration ───────────────────────────────────────────────

@dataclass
class DifferentialExpression:
    gene: str
    log2_fold_change: float
    padj: float
    is_significant: bool       # padj < 0.05
    direction: str             # "UP", "DOWN", "NS"


def parse_deseq2_output(tsv_path: str | Path) -> list[DifferentialExpression]:
    """Parse DESeq2 or edgeR differential expression output.

    Expected columns (tab-separated, with header):
      gene_id (or gene_name), log2FoldChange (or logFC), padj (or FDR)

    Returns list of DifferentialExpression records sorted by |log2FC|.
    """
    path = Path(tsv_path)
    if not path.exists():
        raise FileNotFoundError(f"DE output not found: {tsv_path}")

    results: list[DifferentialExpression] = []

    with open(path, "rt", errors="replace") as fh:
        header_line = fh.readline().strip()
        cols = header_line.split("\t")

        # Flexible column name matching
        gene_col = _find_col(cols, ("gene_id", "gene_name", "gene", "Gene"))
        lfc_col = _find_col(cols, ("log2FoldChange", "logFC", "log2fc", "LFC"))
        padj_col = _find_col(cols, ("padj", "FDR", "adj.P.Val", "q_value"))

        if gene_col is None or lfc_col is None:
            logger.warning("[rnaseq] Could not identify required columns in %s", path.name)
            return []

        for line in fh:
            parts = line.strip().split("\t")
            if len(parts) <= max(filter(None, [gene_col, lfc_col, padj_col])):
                continue
            try:
                gene = parts[gene_col].strip('"')
                lfc = float(parts[lfc_col])
                padj = float(parts[padj_col]) if padj_col is not None else 1.0
                sig = padj < 0.05 and abs(lfc) >= 1.0
                direction = "UP" if lfc >= 1.0 and sig else "DOWN" if lfc <= -1.0 and sig else "NS"
                results.append(DifferentialExpression(
                    gene=gene, log2_fold_change=round(lfc, 4),
                    padj=round(padj, 6), is_significant=sig, direction=direction,
                ))
            except (ValueError, IndexError):
                continue

    results.sort(key=lambda r: abs(r.log2_fold_change), reverse=True)
    logger.info("[rnaseq] Parsed %d DE genes from %s", len(results), path.name)
    return results


def _find_col(cols: list[str], candidates: tuple[str, ...]) -> Optional[int]:
    norm = [c.lower().strip() for c in cols]
    for cand in candidates:
        if cand.lower() in norm:
            return norm.index(cand.lower())
    return None


# ── Fusion gene detection ─────────────────────────────────────────────────────

@dataclass
class FusionEvent:
    fusion_name: str    # e.g. "EML4--ALK"
    gene1: str
    gene2: str
    junction_reads: int
    spanning_reads: int
    confidence: str     # "HIGH", "MEDIUM", "LOW"
    actionable: bool
    recommended_drugs: list[str]
    source: str         # "STAR-Fusion", "Arriba", "manual"


def parse_star_fusion(tsv_path: str | Path) -> list[FusionEvent]:
    """Parse STAR-Fusion output (star-fusion.fusion_predictions.tsv).

    Key columns: #FusionName, JunctionReadCount, SpanningFragCount, est_J,
                 LeftGene, RightGene
    """
    path = Path(tsv_path)
    if not path.exists():
        raise FileNotFoundError(f"STAR-Fusion output not found: {tsv_path}")

    fusions: list[FusionEvent] = []

    with open(path, "rt", errors="replace") as fh:
        header = fh.readline().strip().lstrip("#").split("\t")
        cols = [c.lower().replace("#", "").strip() for c in header]

        fname_col = _find_col(cols, ("fusionname", "fusion_name", "fusion"))
        jrc_col = _find_col(cols, ("junctionreadcount", "junction_read_count", "junction"))
        sfc_col = _find_col(cols, ("spanningfragcount", "spanning_frag_count", "spanning"))

        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if fname_col is None or fname_col >= len(parts):
                continue

            fusion_name = parts[fname_col].replace("--", "-")
            genes = fusion_name.replace("--", "-").split("-")
            gene1 = genes[0] if genes else "UNKNOWN"
            gene2 = genes[1] if len(genes) > 1 else "UNKNOWN"

            jrc = int(parts[jrc_col]) if jrc_col is not None and jrc_col < len(parts) else 0
            sfc = int(parts[sfc_col]) if sfc_col is not None and sfc_col < len(parts) else 0

            # Confidence by read support
            total_reads = jrc + sfc
            if total_reads >= 10:
                confidence = "HIGH"
            elif total_reads >= 3:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            drugs = ACTIONABLE_FUSIONS.get(gene1, []) + ACTIONABLE_FUSIONS.get(gene2, [])
            fusions.append(FusionEvent(
                fusion_name=fusion_name,
                gene1=gene1,
                gene2=gene2,
                junction_reads=jrc,
                spanning_reads=sfc,
                confidence=confidence,
                actionable=bool(drugs),
                recommended_drugs=list(dict.fromkeys(drugs)),  # deduplicate
                source="STAR-Fusion",
            ))

    fusions.sort(key=lambda f: f.junction_reads + f.spanning_reads, reverse=True)
    return fusions


def parse_arriba_fusions(tsv_path: str | Path) -> list[FusionEvent]:
    """Parse Arriba fusion output (fusions.tsv).

    Key columns: gene1, gene2, confidence, breakpoint1, breakpoint2
    """
    path = Path(tsv_path)
    if not path.exists():
        raise FileNotFoundError(f"Arriba output not found: {tsv_path}")

    fusions: list[FusionEvent] = []

    with open(path, "rt", errors="replace") as fh:
        header = fh.readline().strip().lstrip("#").split("\t")
        cols = [c.lower().strip() for c in header]

        g1_col = _find_col(cols, ("gene1",))
        g2_col = _find_col(cols, ("gene2",))
        conf_col = _find_col(cols, ("confidence",))
        reads_col = _find_col(cols, ("split_reads1", "spanning_reads", "read_through"))

        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")

            gene1 = (parts[g1_col].strip() if g1_col is not None and g1_col < len(parts) else "UNKNOWN")
            gene2 = (parts[g2_col].strip() if g2_col is not None and g2_col < len(parts) else "UNKNOWN")
            conf_raw = (parts[conf_col].lower() if conf_col is not None and conf_col < len(parts) else "low")
            confidence = "HIGH" if "high" in conf_raw else "MEDIUM" if "medium" in conf_raw else "LOW"
            reads = int(parts[reads_col]) if reads_col is not None and reads_col < len(parts) else 0

            drugs = ACTIONABLE_FUSIONS.get(gene1, []) + ACTIONABLE_FUSIONS.get(gene2, [])
            fusion_name = f"{gene1}-{gene2}"

            fusions.append(FusionEvent(
                fusion_name=fusion_name,
                gene1=gene1,
                gene2=gene2,
                junction_reads=reads,
                spanning_reads=0,
                confidence=confidence,
                actionable=bool(drugs),
                recommended_drugs=list(dict.fromkeys(drugs)),
                source="Arriba",
            ))

    return fusions


# ── Expression-guided drug re-weighting ──────────────────────────────────────

def apply_expression_weights(
    ranked_candidates: list[dict[str, Any]],
    de_results: list[DifferentialExpression],
    target_gene: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Re-weight drug candidates based on target gene expression level.

    Logic:
      - If target gene is significantly overexpressed (log2FC ≥ 1, padj < 0.05):
        boost drugs targeting it by +0.10 (stronger therapeutic rationale).
      - If target gene is downregulated: note reduced target availability.
      - Drug candidates whose mechanism matches an overexpressed gene are
        also boosted by +0.05.

    Modifies rank_score in-place and adds 'expression_weight_applied' flag.
    Returns re-sorted list.
    """
    gene_lfc: dict[str, DifferentialExpression] = {
        r.gene.upper(): r for r in de_results
    }

    for cand in ranked_candidates:
        boost = 0.0
        expression_note = ""

        # Boost if the primary target gene is overexpressed
        if target_gene and target_gene.upper() in gene_lfc:
            expr = gene_lfc[target_gene.upper()]
            if expr.direction == "UP":
                boost += 0.10
                expression_note = (
                    f"{target_gene} overexpressed (log2FC={expr.log2_fold_change:.2f}, "
                    f"padj={expr.padj:.3f}) — target engagement more likely."
                )
            elif expr.direction == "DOWN":
                boost -= 0.05
                expression_note = (
                    f"{target_gene} downregulated — reduced target availability."
                )

        # Minor boost for any mechanism match with an overexpressed gene
        drug_name = (cand.get("drug_name") or "").upper()
        mechanism = (cand.get("mechanism") or "").upper()
        for gene, expr in gene_lfc.items():
            if expr.direction == "UP" and (gene in drug_name or gene in mechanism):
                boost += 0.05
                expression_note += f" {gene} also overexpressed."
                break

        if boost != 0.0:
            old_score = float(cand.get("rank_score") or 0)
            cand["rank_score"] = round(min(max(old_score + boost, 0.0), 1.0), 4)
            cand["expression_weight_applied"] = True
            cand["expression_note"] = expression_note.strip()
        else:
            cand["expression_weight_applied"] = False

    return sorted(ranked_candidates, key=lambda x: x.get("rank_score", 0), reverse=True)


# ── Tumour microenvironment (TME) ─────────────────────────────────────────────

@dataclass
class TMEProfile:
    """Tumour microenvironment immune deconvolution summary."""
    cd8_t_cell_fraction: Optional[float]
    cd4_t_cell_fraction: Optional[float]
    nk_cell_fraction: Optional[float]
    macrophage_fraction: Optional[float]
    b_cell_fraction: Optional[float]
    immune_phenotype: str   # "INFLAMED", "EXCLUDED", "DESERT"
    immunotherapy_signal: str  # "FAVOURABLE", "UNCERTAIN", "UNFAVOURABLE"
    notes: str


def classify_immune_phenotype(
    cd8_frac: Optional[float],
    total_immune_frac: Optional[float],
) -> tuple[str, str]:
    """Classify TME immune phenotype from CD8+ T-cell and total immune fractions."""
    if cd8_frac is None:
        return "UNKNOWN", "UNCERTAIN"

    if cd8_frac >= 0.10:
        phenotype = "INFLAMED"
        signal = "FAVOURABLE"
    elif (total_immune_frac or 0) >= 0.15 and cd8_frac < 0.05:
        phenotype = "EXCLUDED"
        signal = "UNCERTAIN"
    else:
        phenotype = "DESERT"
        signal = "UNFAVOURABLE"

    return phenotype, signal


# ── Composite multi-omics summary ─────────────────────────────────────────────

@dataclass
class MultiOmicsSummary:
    """Consolidated multi-omics findings for a patient sample."""
    has_rna_data: bool
    has_fusion_data: bool
    de_genes_significant: int
    top_upregulated: list[str]
    top_downregulated: list[str]
    fusions_detected: list[FusionEvent]
    actionable_fusions: list[FusionEvent]
    tme_profile: Optional[TMEProfile]
    expression_boosted_candidates: int
    integration_notes: list[str]


def build_multi_omics_summary(
    de_results: Optional[list[DifferentialExpression]] = None,
    fusions: Optional[list[FusionEvent]] = None,
    tme: Optional[TMEProfile] = None,
    expression_boosted: int = 0,
) -> MultiOmicsSummary:
    """Consolidate multi-omics findings into a structured summary."""
    de = de_results or []
    fus = fusions or []
    sig_de = [r for r in de if r.is_significant]
    up_genes = [r.gene for r in sig_de if r.direction == "UP"][:10]
    down_genes = [r.gene for r in sig_de if r.direction == "DOWN"][:10]
    actionable_fusions = [f for f in fus if f.actionable]

    notes: list[str] = []
    if not de and not fus:
        notes.append("No RNA-seq data provided — analysis based on DNA only.")
    if actionable_fusions:
        fusion_str = ", ".join(f.fusion_name for f in actionable_fusions[:3])
        notes.append(f"Actionable fusions detected: {fusion_str}.")
    if up_genes:
        notes.append(f"Top upregulated targets: {', '.join(up_genes[:5])}.")

    return MultiOmicsSummary(
        has_rna_data=bool(de),
        has_fusion_data=bool(fus),
        de_genes_significant=len(sig_de),
        top_upregulated=up_genes,
        top_downregulated=down_genes,
        fusions_detected=fus,
        actionable_fusions=actionable_fusions,
        tme_profile=tme,
        expression_boosted_candidates=expression_boosted,
        integration_notes=notes,
    )


# ── Tumour Mutational Burden (TMB) ────────────────────────────────────────────
# TMB is defined as the number of somatic non-synonymous mutations per
# megabase of the sequenced genome.  Thresholds from FDA pembrolizumab
# approval (KEYNOTE-158): TMB-High ≥ 10 mut/Mb.
#
# Exome-seq covers ~38 Mb of coding genome (Foundation Medicine uses 1.1 Mb
# of targeted panels; whole-exome is ~38 Mb; whole-genome is ~3000 Mb).
# For VCF-based estimates, caller panel size should be used if known.

_WES_CODING_MB: float = 38.0   # typical WES covered coding bases (Mb)
_PANEL_TMB_MB: float = 1.14    # Foundation Medicine FoundationOne CDx panel (Mb)


@dataclass
class TumorMutationalBurden:
    """Tumour Mutational Burden estimate from somatic variant count."""
    total_somatic_variants: int
    genome_size_mb: float
    tmb_per_mb: float
    tmb_class: str           # "LOW", "INTERMEDIATE", "HIGH", "VERY_HIGH"
    immunotherapy_relevant: bool
    notes: str


def calculate_tmb(
    somatic_variant_count: int,
    genome_size_mb: float = _WES_CODING_MB,
    filter_synonymous: bool = True,
) -> TumorMutationalBurden:
    """Calculate TMB from variant count and sequencing panel size.

    Args:
        somatic_variant_count: Number of somatic mutations called (non-synonymous
            if filter_synonymous=True was applied upstream by the variant caller).
        genome_size_mb: Size of sequenced region in megabases. Default is WES
            (~38 Mb). Use 1.14 Mb for FoundationOne CDx, ~3000 Mb for WGS.
        filter_synonymous: If True, notes that only non-synonymous SNVs were
            counted (consistent with FDA TMB definition).

    Returns:
        TumorMutationalBurden with TMB per Mb and FDA-aligned classification.

    Classification thresholds (FDA KEYNOTE-158, Merck label):
        TMB-Low       < 5 mut/Mb
        TMB-Intermediate  5–9 mut/Mb
        TMB-High      10–19 mut/Mb  ← pembrolizumab FDA-approved (agnostic)
        TMB-Very-High ≥ 20 mut/Mb
    """
    if genome_size_mb <= 0:
        genome_size_mb = _WES_CODING_MB

    tmb = somatic_variant_count / genome_size_mb

    if tmb >= 20:
        tmb_class = "VERY_HIGH"
        ici_relevant = True
        notes = (
            f"TMB-Very-High ({tmb:.1f} mut/Mb). Strong signal for immune checkpoint "
            "inhibitor benefit. Consider pembrolizumab (FDA agnostic approval ≥10 mut/Mb)."
        )
    elif tmb >= 10:
        tmb_class = "HIGH"
        ici_relevant = True
        notes = (
            f"TMB-High ({tmb:.1f} mut/Mb). Meets FDA threshold for pembrolizumab "
            "agnostic approval. ICI therapy is likely to be beneficial."
        )
    elif tmb >= 5:
        tmb_class = "INTERMEDIATE"
        ici_relevant = False
        notes = (
            f"TMB-Intermediate ({tmb:.1f} mut/Mb). Below FDA TMB-High threshold. "
            "ICI benefit uncertain; combine with other predictive biomarkers (MSI, PD-L1)."
        )
    else:
        tmb_class = "LOW"
        ici_relevant = False
        notes = (
            f"TMB-Low ({tmb:.1f} mut/Mb). Low mutational burden; ICI monotherapy "
            "unlikely to be effective based on TMB alone."
        )

    if filter_synonymous:
        notes += " (Count based on non-synonymous somatic mutations.)"

    return TumorMutationalBurden(
        total_somatic_variants=somatic_variant_count,
        genome_size_mb=round(genome_size_mb, 2),
        tmb_per_mb=round(tmb, 2),
        tmb_class=tmb_class,
        immunotherapy_relevant=ici_relevant,
        notes=notes,
    )


def count_vcf_somatic_variants(vcf_path: str) -> int:
    """Count non-synonymous somatic variant lines in a VCF file.

    Filters out:
      - Header lines (starting with #)
      - Germline-only calls (FILTER column contains 'germline')
      - Synonymous calls if CSQ/ANN INFO field indicates 'synonymous_variant'

    For a rough TMB estimate, non-filtered variant count is used when
    annotation fields are absent.
    """
    from pathlib import Path
    count = 0
    p = Path(vcf_path)
    if not p.exists():
        raise FileNotFoundError(f"VCF not found: {vcf_path}")

    with open(p, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 7:
                continue
            filter_col = parts[6].upper() if len(parts) > 6 else "."
            if "GERMLINE" in filter_col:
                continue
            # If CSQ/ANN annotation is available, skip synonymous variants
            info = parts[7] if len(parts) > 7 else ""
            if "synonymous_variant" in info.lower():
                continue
            count += 1

    return count


# ── MSI (Microsatellite Instability) classification ───────────────────────────
# MSI-H is an FDA-approved biomarker for pembrolizumab regardless of tumour type
# (KEYNOTE-016 / 158 / 164 / 169 / 170 / 172). MSS tumours are immunotherapy
# resistant except in specific contexts (e.g., combined with anti-VEGF in CRC).

@dataclass
class MSIStatus:
    """Microsatellite instability classification from MSISensor2 or MANTIS output."""
    msi_score: Optional[float]    # MSISensor2 score (% unstable loci)
    mantis_score: Optional[float] # MANTIS score (>0.4 = MSI-H)
    msi_class: str                # "MSI-H", "MSI-L", "MSS", "UNKNOWN"
    immunotherapy_relevant: bool
    source: str                   # "MSISensor2", "MANTIS", "clinical_report", "unknown"
    notes: str


def classify_msi_from_msisensor2(score: float) -> MSIStatus:
    """Classify MSI status from MSISensor2 percentage score.

    MSISensor2 threshold (default): ≥ 20% unstable loci = MSI-H.
    Reference: Niu et al., Genome Medicine 2014.
    """
    if score >= 20.0:
        msi_class = "MSI-H"
        relevant = True
        notes = (
            f"MSI-High (MSISensor2 score {score:.1f}% ≥ 20%). "
            "Meets FDA threshold for pembrolizumab agnostic approval. "
            "Also consider nivolumab, dostarlimab per tumour type."
        )
    elif score >= 10.0:
        msi_class = "MSI-L"
        relevant = False
        notes = (
            f"MSI-Low (MSISensor2 score {score:.1f}%). "
            "Below MSI-H threshold; ICI benefit based on MSI alone is uncertain."
        )
    else:
        msi_class = "MSS"
        relevant = False
        notes = (
            f"Microsatellite Stable (MSISensor2 score {score:.1f}%). "
            "ICI monotherapy unlikely to provide benefit via MSI pathway."
        )

    return MSIStatus(
        msi_score=round(score, 2),
        mantis_score=None,
        msi_class=msi_class,
        immunotherapy_relevant=relevant,
        source="MSISensor2",
        notes=notes,
    )


def classify_msi_from_mantis(score: float) -> MSIStatus:
    """Classify MSI status from MANTIS score.

    MANTIS threshold: > 0.4 = MSI-H.
    Reference: Kautto et al., Oncotarget 2017.
    """
    if score > 0.4:
        msi_class = "MSI-H"
        relevant = True
        notes = (
            f"MSI-High (MANTIS score {score:.3f} > 0.4). "
            "Consistent with MMR-deficiency; pembrolizumab agnostic approval applies."
        )
    else:
        msi_class = "MSS"
        relevant = False
        notes = (
            f"Microsatellite Stable (MANTIS score {score:.3f} ≤ 0.4)."
        )

    return MSIStatus(
        msi_score=None,
        mantis_score=round(score, 4),
        msi_class=msi_class,
        immunotherapy_relevant=relevant,
        source="MANTIS",
        notes=notes,
    )


def parse_msi_from_clinical_string(text: str) -> MSIStatus:
    """Parse MSI status from a free-text pathology report field.

    Recognises common representations: 'MSI-H', 'MSI-High', 'MSI High',
    'dMMR', 'pMMR', 'MSS', 'MSI-L', 'MSI-Low'.
    """
    t = text.strip().upper().replace("-", "").replace(" ", "")
    if any(k in t for k in ("MSIH", "MSIHIGH", "DMMR")):
        msi_class = "MSI-H"
        relevant = True
        notes = f"MSI-High reported in clinical pathology: '{text}'."
    elif any(k in t for k in ("MSS", "PMMR")):
        msi_class = "MSS"
        relevant = False
        notes = f"Microsatellite Stable reported in clinical pathology: '{text}'."
    elif any(k in t for k in ("MSIL", "MSILOW")):
        msi_class = "MSI-L"
        relevant = False
        notes = f"MSI-Low reported in clinical pathology: '{text}'."
    else:
        msi_class = "UNKNOWN"
        relevant = False
        notes = f"MSI status not determinable from string: '{text}'."

    return MSIStatus(
        msi_score=None,
        mantis_score=None,
        msi_class=msi_class,
        immunotherapy_relevant=relevant,
        source="clinical_report",
        notes=notes,
    )


# ── Immunotherapy context weighting ──────────────────────────────────────────
# When TMB-High or MSI-H is detected, boost known ICI drugs in the candidate
# list and inject any that are missing.

_ICI_DRUGS: dict[str, str] = {
    "pembrolizumab": "LEVEL_1",   # FDA agnostic TMB-H and MSI-H
    "nivolumab": "LEVEL_1",       # MSI-H CRC, gastric
    "dostarlimab": "LEVEL_1",     # MMR-deficient endometrial
    "ipilimumab": "LEVEL_2",      # combo with nivolumab MSI-H CRC
    "atezolizumab": "LEVEL_2",    # NSCLC, bladder PD-L1+
    "durvalumab": "LEVEL_2",      # NSCLC, biliary
    "avelumab": "LEVEL_2",        # Merkel cell, urothelial
}

_ICI_BOOST = 0.12  # rank_score additive boost for ICI drugs when biomarker confirmed


def apply_immunotherapy_context(
    candidates: list[dict[str, Any]],
    tmb: Optional[TumorMutationalBurden] = None,
    msi: Optional[MSIStatus] = None,
) -> list[dict[str, Any]]:
    """Boost and inject ICI candidates when TMB-High or MSI-H is confirmed.

    Rules:
      - If TMB-High (≥10 mut/Mb) or MSI-H: boost all ICI drugs by _ICI_BOOST.
      - Inject missing ICI drugs with their LEVEL_1/2 annotation.
      - Record the biomarker trigger in 'immunotherapy_context' field.
      - If neither TMB-High nor MSI-H, apply a mild penalty (-0.05) to ICI
        drugs to reflect the lower prior probability of benefit.

    Returns re-sorted list by rank_score.
    """
    import re

    is_ici_indicated = (
        (tmb is not None and tmb.immunotherapy_relevant) or
        (msi is not None and msi.immunotherapy_relevant)
    )

    trigger_notes = []
    if tmb and tmb.immunotherapy_relevant:
        trigger_notes.append(f"TMB-{tmb.tmb_class} ({tmb.tmb_per_mb:.1f} mut/Mb)")
    if msi and msi.immunotherapy_relevant:
        trigger_notes.append(f"{msi.msi_class} ({msi.source})")
    trigger_str = " + ".join(trigger_notes) if trigger_notes else "no ICI biomarker"

    def _norm(name: str) -> str:
        return re.sub(r"[\s\-.]", "", name.lower())

    existing_norms = {_norm(c.get("drug_name") or "") for c in candidates}

    for cand in candidates:
        dn = _norm(cand.get("drug_name") or "")
        for ici_drug in _ICI_DRUGS:
            if _norm(ici_drug) in dn or dn in _norm(ici_drug):
                if is_ici_indicated:
                    old = float(cand.get("rank_score") or 0)
                    cand["rank_score"] = round(min(old + _ICI_BOOST, 1.0), 4)
                    cand["immunotherapy_context"] = f"Boosted: {trigger_str}"
                else:
                    old = float(cand.get("rank_score") or 0)
                    cand["rank_score"] = round(max(old - 0.05, 0.0), 4)
                    cand["immunotherapy_context"] = "Mild penalty: no ICI biomarker (TMB-Low, MSS)"
                break

    if is_ici_indicated:
        for ici_drug, level in _ICI_DRUGS.items():
            dn = _norm(ici_drug)
            if not any(dn in e or e in dn for e in existing_norms):
                candidates.append({
                    "drug_name": ici_drug.title(),
                    "is_approved": level == "LEVEL_1",
                    "max_phase": "APPROVAL" if level == "LEVEL_1" else "PHASE3",
                    "opentargets_score": None,
                    "oncokb_level": level,
                    "chembl_id": None,
                    "binding_score": None,
                    "immunotherapy_context": f"Injected: {trigger_str}",
                    "_injected_from_ici_context": True,
                })
                existing_norms.add(dn)

    return sorted(candidates, key=lambda x: x.get("rank_score", 0), reverse=True)
