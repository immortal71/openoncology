"""Multi-cohort / study browser API — Phase 2.

Endpoints:
  GET  /api/cohorts/studies               — list all public studies
  GET  /api/cohorts/studies/{study_id}    — study details + sample count
  GET  /api/cohorts/{study_id}/mutations  — paginated mutations in a study
                                            ?gene=KRAS&classification=Missense_Mutation
  GET  /api/cohorts/cross-study           — alteration frequency across studies
                                            ?gene=EGFR&alteration=L858R
  GET  /api/cohorts/oncoprint             — OncoPrint data for a set of genes
                                            ?study_id=tcga_luad&genes=EGFR,KRAS,TP53
  GET  /api/cohorts/gene-summary          — per-gene summary across all studies
                                            ?gene=KRAS

All endpoints that return cohort/study data are public (no auth required) to
enable research use.  Patient-submitted data is never included in cohort
endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.cohort import CohortMutation, Sample, Study

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cohorts", tags=["cohorts"])


# ── Study listing ──────────────────────────────────────────────────────────────

@router.get("/studies")
async def list_studies(
    cancer_type: Optional[str] = Query(None, description="Filter by cancer type ID (e.g. LUAD, BRCA)"),
    source: Optional[str] = Query(None, description="Filter by data source (TCGA, ICGC, GEO)"),
    db: AsyncSession = Depends(get_db),
):
    """List all public genomic studies available for browsing."""
    stmt = select(Study).where(Study.is_public.is_(True))  # noqa: E712
    if cancer_type:
        stmt = stmt.where(Study.cancer_type == cancer_type.upper())
    if source:
        stmt = stmt.where(Study.source == source)
    stmt = stmt.order_by(Study.sample_count.desc())

    rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": len(rows),
        "studies": [_study_to_dict(s) for s in rows],
    }


@router.get("/studies/{study_id}")
async def get_study(
    study_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a single study by its study_id."""
    study = (await db.execute(
        select(Study).where(Study.study_id == study_id)
    )).scalar_one_or_none()

    if not study:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    # Count samples
    sample_count = await db.scalar(
        select(func.count()).select_from(Sample).where(Sample.study_id == study.id)
    )
    # Count distinct genes mutated
    gene_count = await db.scalar(
        select(func.count(func.distinct(CohortMutation.gene)))
        .select_from(CohortMutation)
        .where(CohortMutation.study_id == study.id)
    )

    return {
        **_study_to_dict(study),
        "sample_count_live": sample_count or 0,
        "distinct_genes_mutated": gene_count or 0,
    }


# ── Study mutation queries ─────────────────────────────────────────────────────

@router.get("/{study_id}/mutations")
async def get_study_mutations(
    study_id: str,
    gene: Optional[str] = Query(None, description="Filter by gene symbol (e.g. KRAS)"),
    classification: Optional[str] = Query(None, description="Filter by variant classification"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated somatic mutations for a study, optionally filtered by gene."""
    study = (await db.execute(
        select(Study).where(Study.study_id == study_id)
    )).scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    stmt = select(CohortMutation).where(CohortMutation.study_id == study.id)
    if gene:
        stmt = stmt.where(CohortMutation.gene == gene.upper())
    if classification:
        stmt = stmt.where(CohortMutation.variant_classification == classification)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    mutations = (await db.execute(stmt)).scalars().all()

    return {
        "study_id": study_id,
        "gene_filter": gene,
        "total": total,
        "page": page,
        "per_page": per_page,
        "mutations": [_mutation_to_dict(m) for m in mutations],
    }


# ── Cross-study frequency ──────────────────────────────────────────────────────

@router.get("/cross-study")
async def get_cross_study_frequency(
    gene: str = Query(..., description="Hugo gene symbol (e.g. EGFR)"),
    alteration: Optional[str] = Query(None, description="Protein change (e.g. L858R)"),
    db: AsyncSession = Depends(get_db),
):
    """Return alteration frequency across all public studies for a gene.

    This is the cBioPortal 'Summary' view: how often is this gene/alteration
    mutated in each cancer cohort?
    """
    gene_upper = gene.upper()

    # Base query: count mutations per study
    mut_stmt = (
        select(
            CohortMutation.study_id,
            func.count().label("mutation_count"),
        )
        .where(CohortMutation.gene == gene_upper)
    )
    if alteration:
        mut_stmt = mut_stmt.where(CohortMutation.protein_change == alteration)
    mut_stmt = mut_stmt.group_by(CohortMutation.study_id)

    mut_rows = (await db.execute(mut_stmt)).all()
    if not mut_rows:
        return {
            "gene": gene_upper,
            "alteration": alteration,
            "total_studies_with_alteration": 0,
            "frequency_by_study": [],
        }

    # Fetch study metadata and sample counts in one query
    study_ids = [r.study_id for r in mut_rows]
    studies_stmt = select(Study).where(Study.id.in_(study_ids))
    studies_by_id = {
        s.id: s
        for s in (await db.execute(studies_stmt)).scalars().all()
    }

    # Fetch sample counts per study
    sample_counts = dict(
        (await db.execute(
            select(Sample.study_id, func.count().label("n"))
            .where(Sample.study_id.in_(study_ids))
            .group_by(Sample.study_id)
        )).all()
    )

    results = []
    for row in mut_rows:
        study = studies_by_id.get(row.study_id)
        if not study:
            continue
        n_samples = sample_counts.get(row.study_id, study.sample_count or 1)
        freq = round(row.mutation_count / n_samples, 4) if n_samples else None
        results.append({
            "study_id": study.study_id,
            "study_name": study.name,
            "cancer_type": study.cancer_type,
            "cancer_type_label": study.cancer_type_label,
            "mutation_count": row.mutation_count,
            "sample_count": n_samples,
            "frequency": freq,
            "frequency_pct": round(freq * 100, 2) if freq is not None else None,
        })

    results.sort(key=lambda x: x["frequency"] or 0, reverse=True)
    return {
        "gene": gene_upper,
        "alteration": alteration,
        "total_studies_with_alteration": len(results),
        "frequency_by_study": results,
    }


# ── OncoPrint data ─────────────────────────────────────────────────────────────

@router.get("/oncoprint")
async def get_oncoprint_data(
    study_id: str = Query(..., description="Study ID to draw OncoPrint for"),
    genes: str = Query(..., description="Comma-separated gene list (e.g. EGFR,KRAS,TP53)"),
    max_samples: int = Query(200, ge=1, le=1000, description="Max samples to include"),
    db: AsyncSession = Depends(get_db),
):
    """Return OncoPrint-formatted alteration matrix for a gene panel in a study.

    Response format:
      genes: [str]
      samples: [str]
      alterations: {gene: {sample_id: [alteration_type, ...]}}
    """
    study = (await db.execute(
        select(Study).where(Study.study_id == study_id)
    )).scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    gene_list = [g.strip().upper() for g in genes.split(",") if g.strip()]
    if not gene_list:
        raise HTTPException(status_code=422, detail="At least one gene required")

    # Fetch all mutations for the requested genes in this study
    stmt = (
        select(CohortMutation)
        .join(Sample, Sample.id == CohortMutation.sample_id)
        .where(
            CohortMutation.study_id == study.id,
            CohortMutation.gene.in_(gene_list),
        )
        .limit(max_samples * len(gene_list) * 5)
    )
    mutations = (await db.execute(stmt)).scalars().all()

    # Fetch samples for ordering (by alteration count descending)
    all_sample_ids: set[str] = {m.sample_id for m in mutations}
    samples_stmt = select(Sample).where(Sample.id.in_(all_sample_ids)).limit(max_samples)
    samples = (await db.execute(samples_stmt)).scalars().all()
    sample_external_ids = {s.id: s.sample_id for s in samples}

    # Build alteration matrix
    # alterations[gene][sample_external_id] = list of classification strings
    alteration_matrix: dict[str, dict[str, list[str]]] = {g: {} for g in gene_list}
    for m in mutations:
        gene = m.gene.upper()
        if gene not in alteration_matrix:
            continue
        ext_id = sample_external_ids.get(m.sample_id, m.sample_id)
        if ext_id not in alteration_matrix[gene]:
            alteration_matrix[gene][ext_id] = []
        alt_type = m.variant_classification or "Mutation"
        if alt_type not in alteration_matrix[gene][ext_id]:
            alteration_matrix[gene][ext_id].append(alt_type)

    # Order samples: most altered first
    sample_alteration_counts = {
        ext_id: sum(1 for g in gene_list if alteration_matrix[g].get(ext_id))
        for ext_id in sample_external_ids.values()
    }
    ordered_samples = sorted(
        sample_external_ids.values(),
        key=lambda s: sample_alteration_counts.get(s, 0),
        reverse=True,
    )[:max_samples]

    # Compute per-gene alteration frequency
    gene_frequencies = {
        gene: round(
            sum(1 for s in ordered_samples if alteration_matrix[gene].get(s)) / len(ordered_samples), 3
        ) if ordered_samples else 0
        for gene in gene_list
    }

    # Order genes by frequency
    ordered_genes = sorted(gene_list, key=lambda g: gene_frequencies.get(g, 0), reverse=True)

    return {
        "study_id": study_id,
        "genes": ordered_genes,
        "samples": ordered_samples,
        "sample_count": len(ordered_samples),
        "gene_frequencies": gene_frequencies,
        "alterations": {g: alteration_matrix[g] for g in ordered_genes},
    }


# ── Gene summary ───────────────────────────────────────────────────────────────

@router.get("/gene-summary")
async def get_gene_summary(
    gene: str = Query(..., description="Hugo gene symbol"),
    db: AsyncSession = Depends(get_db),
):
    """Return a summary of mutations for a gene across all public studies.

    Includes top altered residues (protein changes), alteration frequency
    by variant classification, and studies that contain this gene.
    """
    gene_upper = gene.upper()

    # Top protein changes
    top_changes = (await db.execute(
        select(CohortMutation.protein_change, func.count().label("n"))
        .where(CohortMutation.gene == gene_upper)
        .where(CohortMutation.protein_change.isnot(None))
        .group_by(CohortMutation.protein_change)
        .order_by(func.count().desc())
        .limit(20)
    )).all()

    # Variant classification breakdown
    class_counts = (await db.execute(
        select(CohortMutation.variant_classification, func.count().label("n"))
        .where(CohortMutation.gene == gene_upper)
        .group_by(CohortMutation.variant_classification)
        .order_by(func.count().desc())
    )).all()

    # Studies containing this gene
    study_ids = (await db.execute(
        select(func.distinct(CohortMutation.study_id))
        .where(CohortMutation.gene == gene_upper)
    )).scalars().all()

    studies = (await db.execute(
        select(Study).where(Study.id.in_(study_ids))
    )).scalars().all()

    # Hotspot annotation for top protein changes
    from services.hotspot import get_hotspot_info
    top_with_hotspot = [
        {
            "protein_change": row.protein_change,
            "count": row.n,
            "is_hotspot": get_hotspot_info(gene_upper, row.protein_change or "") is not None,
        }
        for row in top_changes
    ]

    return {
        "gene": gene_upper,
        "total_mutations": sum(r.n for r in top_changes),
        "top_protein_changes": top_with_hotspot,
        "variant_classification_breakdown": [
            {"classification": r.variant_classification or "Unknown", "count": r.n}
            for r in class_counts
        ],
        "studies": [_study_to_dict(s) for s in studies],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _study_to_dict(s: Study) -> dict:
    return {
        "id": s.id,
        "study_id": s.study_id,
        "name": s.name,
        "description": s.description,
        "cancer_type": s.cancer_type,
        "cancer_type_label": s.cancer_type_label,
        "sample_count": s.sample_count,
        "data_types": s.data_types,
        "reference_genome": s.reference_genome,
        "pmid": s.pmid,
        "source": s.source,
    }


def _mutation_to_dict(m: CohortMutation) -> dict:
    return {
        "gene": m.gene,
        "protein_change": m.protein_change,
        "hgvs_c": m.hgvs_c,
        "variant_classification": m.variant_classification,
        "chromosome": m.chromosome,
        "position": m.position,
        "ref_allele": m.ref_allele,
        "alt_allele": m.alt_allele,
        "vaf": m.vaf,
        "oncokb_level": m.oncokb_level,
    }
