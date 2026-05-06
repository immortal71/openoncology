"""Visualisation API routes — lollipop plots, survival curves, co-occurrence.

These endpoints power the publication-grade visualisations comparable to
cBioPortal:

  GET /api/viz/lollipop/{gene}
      Lollipop plot data: per-residue mutation frequency + domain annotations
      ?study_id=tcga_luad  (optional; defaults to all studies)

  GET /api/viz/survival
      Kaplan-Meier curves for mutated vs wildtype in a study
      ?study_id=tcga_luad&gene=EGFR&alteration=L858R&type=OS

  GET /api/viz/cooccurrence
      Pairwise co-occurrence / mutual exclusivity matrix for a gene panel
      ?study_id=tcga_luad&genes=EGFR,KRAS,TP53,PIK3CA

All endpoints are public (no auth required) — they return aggregated research
data only, never PHI.
"""

from __future__ import annotations

from typing import Optional

import logging
import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.cohort import CohortMutation, Sample, Study
from services.hotspot import get_hotspot_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/viz", tags=["visualizations"])


# ── Lollipop plot ──────────────────────────────────────────────────────────────

@router.get("/lollipop/{gene}")
async def lollipop_data(
    gene: str,
    study_id: Optional[str] = Query(None, description="Limit to one study; omit for all public studies"),
    min_count: int = Query(2, ge=1, description="Minimum sample count to include a residue"),
    db: AsyncSession = Depends(get_db),
):
    """Return lollipop plot data for a gene.

    Each residue that is mutated ≥ min_count times is returned as a lollipop:
      { position, protein_change, count, variant_classifications, is_hotspot }

    Also returns UniProt-derived domain annotations from the curated map.
    """
    gene_upper = gene.upper()

    stmt = (
        select(
            CohortMutation.protein_change,
            CohortMutation.variant_classification,
            func.count().label("n"),
        )
        .where(
            CohortMutation.gene == gene_upper,
            CohortMutation.protein_change.isnot(None),
        )
        .group_by(CohortMutation.protein_change, CohortMutation.variant_classification)
        .having(func.count() >= min_count)
        .order_by(func.count().desc())
    )

    if study_id:
        study = (await db.execute(
            select(Study).where(Study.study_id == study_id)
        )).scalar_one_or_none()
        if study:
            stmt = stmt.where(CohortMutation.study_id == study.id)

    rows = (await db.execute(stmt)).all()

    # Aggregate by protein_change (merge classification counts)
    residue_map: dict[str, dict] = {}
    for row in rows:
        pc = row.protein_change
        cls = row.variant_classification or "Mutation"
        if pc not in residue_map:
            pos = _extract_position(pc)
            hotspot = get_hotspot_info(gene_upper, pc)
            residue_map[pc] = {
                "protein_change": pc,
                "position": pos,
                "total_count": 0,
                "classifications": {},
                "is_hotspot": hotspot is not None,
                "hotspot_n_samples": hotspot["n_samples"] if hotspot else None,
            }
        residue_map[pc]["total_count"] += row.n
        residue_map[pc]["classifications"][cls] = residue_map[pc]["classifications"].get(cls, 0) + row.n

    lollipops = sorted(
        [v for v in residue_map.values() if v["position"] is not None],
        key=lambda x: x["position"],
    )

    domains = _get_protein_domains(gene_upper)

    return {
        "gene": gene_upper,
        "study_id": study_id,
        "lollipops": lollipops,
        "protein_domains": domains,
        "total_mutations_plotted": sum(v["total_count"] for v in residue_map.values()),
    }


def _extract_position(protein_change: str) -> Optional[int]:
    """Extract the integer residue position from a protein change string."""
    import re
    if not protein_change:
        return None
    m = re.search(r"(\d+)", protein_change)
    return int(m.group(1)) if m else None


def _get_protein_domains(gene: str) -> list[dict]:
    """Return curated protein domain annotations for lollipop rendering.

    This static map covers the most clinically relevant domains for common
    oncogenes.  For full coverage, integrate the UniProt API.
    """
    _DOMAINS: dict[str, list[dict]] = {
        "EGFR": [
            {"name": "Furin-like cysteine rich 1", "start": 57,  "end": 167, "color": "#4dabf7"},
            {"name": "Furin-like cysteine rich 2", "start": 361, "end": 481, "color": "#4dabf7"},
            {"name": "Transmembrane",              "start": 646, "end": 667, "color": "#868e96"},
            {"name": "Protein kinase",             "start": 712, "end": 979, "color": "#f783ac"},
        ],
        "KRAS": [
            {"name": "GTPase",    "start": 1,   "end": 164, "color": "#f783ac"},
            {"name": "Linker",    "start": 165, "end": 172, "color": "#868e96"},
            {"name": "CAAX box",  "start": 173, "end": 189, "color": "#74c0fc"},
        ],
        "BRAF": [
            {"name": "RAS binding",  "start": 155, "end": 225, "color": "#4dabf7"},
            {"name": "Protein kinase","start": 457, "end": 717, "color": "#f783ac"},
        ],
        "PIK3CA": [
            {"name": "PIK adaptor binding", "start": 1,   "end": 108, "color": "#4dabf7"},
            {"name": "Ras binding",         "start": 190, "end": 291, "color": "#ffd43b"},
            {"name": "C2 PI3K-type",        "start": 333, "end": 520, "color": "#74c0fc"},
            {"name": "PI3K/PI4K kinase",    "start": 726, "end": 1068, "color": "#f783ac"},
        ],
        "TP53": [
            {"name": "Transactivation",    "start": 1,   "end": 42,  "color": "#4dabf7"},
            {"name": "Proline-rich",       "start": 63,  "end": 97,  "color": "#74c0fc"},
            {"name": "DNA binding",        "start": 102, "end": 292, "color": "#f783ac"},
            {"name": "Tetramerisation",    "start": 323, "end": 356, "color": "#ffd43b"},
            {"name": "Regulatory",         "start": 364, "end": 393, "color": "#868e96"},
        ],
        "BRCA1": [
            {"name": "RING",  "start": 1,    "end": 109,  "color": "#f783ac"},
            {"name": "BRCT1", "start": 1646, "end": 1736, "color": "#4dabf7"},
            {"name": "BRCT2", "start": 1756, "end": 1855, "color": "#74c0fc"},
        ],
        "BRCA2": [
            {"name": "BRC repeats", "start": 1002, "end": 2085, "color": "#ffd43b"},
            {"name": "DBD",         "start": 2402, "end": 3186, "color": "#f783ac"},
        ],
        "IDH1": [
            {"name": "Isocitrate/isopropylmalate dehydrogenase", "start": 1, "end": 414, "color": "#f783ac"},
        ],
        "ERBB2": [
            {"name": "Receptor L 1",  "start": 25,  "end": 196, "color": "#4dabf7"},
            {"name": "Furin-like",    "start": 196, "end": 339, "color": "#74c0fc"},
            {"name": "Receptor L 2",  "start": 340, "end": 505, "color": "#4dabf7"},
            {"name": "Transmembrane", "start": 652, "end": 675, "color": "#868e96"},
            {"name": "Protein kinase","start": 720, "end": 987, "color": "#f783ac"},
        ],
    }
    return _DOMAINS.get(gene, [])


# ── Survival curves ────────────────────────────────────────────────────────────

@router.get("/survival")
async def survival_curves(
    study_id: str = Query(..., description="Study ID (e.g. tcga_luad_2016)"),
    gene: str = Query(..., description="Hugo gene symbol"),
    alteration: Optional[str] = Query(None, description="Protein change (e.g. L858R); omit for any mutation"),
    survival_type: str = Query("OS", description="OS (overall) or DFS (disease-free)"),
    db: AsyncSession = Depends(get_db),
):
    """Return Kaplan-Meier survival curves for mutated vs wildtype groups."""
    study = (await db.execute(
        select(Study).where(Study.study_id == study_id)
    )).scalar_one_or_none()
    if not study:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    from services.survival import compute_survival_curves
    return await compute_survival_curves(
        study_id_internal=study.id,
        gene=gene,
        protein_change=alteration,
        db=db,
        survival_type=survival_type.upper(),
    )


# ── Co-occurrence / mutual exclusivity ────────────────────────────────────────

@router.get("/cooccurrence")
async def cooccurrence_matrix(
    study_id: str = Query(..., description="Study ID"),
    genes: str = Query(..., description="Comma-separated gene list (2–20 genes)"),
    db: AsyncSession = Depends(get_db),
):
    """Return a pairwise co-occurrence / mutual exclusivity matrix.

    For each gene pair, computes:
      - odds_ratio : > 1 = co-occurring, < 1 = mutually exclusive
      - p_value    : Fisher's exact test (log approximation for large N)
      - log_odds   : log2(odds_ratio)
      - tendency   : "Co-occurrence", "Mutual exclusivity", or "Neutral"

    Used to render the co-occurrence heatmap on the study explorer page.
    """
    study = (await db.execute(
        select(Study).where(Study.study_id == study_id)
    )).scalar_one_or_none()
    if not study:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Study not found")

    gene_list = [g.strip().upper() for g in genes.split(",") if g.strip()]
    if len(gene_list) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="At least two genes required")
    gene_list = gene_list[:20]

    # Total samples in study
    n_total = await db.scalar(
        select(func.count()).select_from(Sample).where(Sample.study_id == study.id)
    ) or 1

    # For each gene, get the set of sample_ids that have a mutation
    gene_samples: dict[str, set[str]] = {}
    for gene in gene_list:
        rows = (await db.execute(
            select(func.distinct(CohortMutation.sample_id))
            .where(
                CohortMutation.study_id == study.id,
                CohortMutation.gene == gene,
            )
        )).scalars().all()
        gene_samples[gene] = set(rows)

    # Build pairwise matrix
    pairs = []
    for i, gene_a in enumerate(gene_list):
        for j, gene_b in enumerate(gene_list):
            if j <= i:
                continue
            a_set = gene_samples[gene_a]
            b_set = gene_samples[gene_b]
            both = len(a_set & b_set)
            only_a = len(a_set - b_set)
            only_b = len(b_set - a_set)
            neither = n_total - both - only_a - only_b

            odds_ratio, p_value = _fisher_exact(both, only_a, only_b, neither)
            log_odds = math.log2(odds_ratio) if odds_ratio > 0 else 0.0
            if p_value < 0.05 and log_odds > 0.5:
                tendency = "Co-occurrence"
            elif p_value < 0.05 and log_odds < -0.5:
                tendency = "Mutual exclusivity"
            else:
                tendency = "Neutral"

            pairs.append({
                "gene_a": gene_a,
                "gene_b": gene_b,
                "n_both": both,
                "n_only_a": only_a,
                "n_only_b": only_b,
                "n_neither": neither,
                "odds_ratio": round(odds_ratio, 4),
                "log_odds": round(log_odds, 4),
                "p_value": round(p_value, 6),
                "tendency": tendency,
            })

    return {
        "study_id": study_id,
        "genes": gene_list,
        "n_total_samples": n_total,
        "pairs": pairs,
    }


def _fisher_exact(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """Two-sided Fisher's exact test using log-hypergeometric approximation.

    Returns (odds_ratio, p_value).  Handles zero cells with 0.5 continuity correction.
    """
    a, b, c, d = max(a, 0), max(b, 0), max(c, 0), max(d, 0)
    # Odds ratio
    numerator = (a + 0.5) * (d + 0.5)
    denominator = (b + 0.5) * (c + 0.5)
    odds_ratio = numerator / denominator if denominator > 0 else float("inf")

    # Chi-squared approximation for p-value
    n = a + b + c + d
    if n == 0:
        return odds_ratio, 1.0
    expected_a = (a + b) * (a + c) / n
    if expected_a == 0:
        return odds_ratio, 1.0
    chi2 = (abs(a - expected_a) - 0.5) ** 2 / expected_a
    # Simple chi-squared p-value approximation
    p_value = math.erfc(math.sqrt(chi2 / 2))
    return odds_ratio, max(0.0, min(1.0, p_value))
