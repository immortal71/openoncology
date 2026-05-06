"""GraphQL schema — Strawberry-based FHIR-friendly API.

Exposes:
  - studies          — list public genomic studies
  - studyMutations   — mutations for a gene in a study
  - crossStudyFreq   — alteration frequency across all studies
  - geneSummary      — top mutations + pathway context for a gene
  - survivalCurves   — KM curve data for a gene in a study
  - oncoPrint        — OncoPrint alteration matrix

Mount at /graphql in main.py.

Requires strawberry-graphql:
  pip install "strawberry-graphql[fastapi]"
"""

from __future__ import annotations

from typing import Optional, List

import strawberry
from strawberry.fastapi import GraphQLRouter


# ── Types ──────────────────────────────────────────────────────────────────────

@strawberry.type
class StudyType:
    study_id: str
    name: str
    cancer_type: Optional[str]
    cancer_type_label: Optional[str]
    sample_count: int
    reference_genome: Optional[str]
    pmid: Optional[str]
    source: Optional[str]
    data_types: Optional[strawberry.scalars.JSON]


@strawberry.type
class CohortMutationType:
    gene: str
    protein_change: Optional[str]
    hgvs_c: Optional[str]
    variant_classification: Optional[str]
    chromosome: Optional[str]
    position: Optional[int]
    ref_allele: Optional[str]
    alt_allele: Optional[str]
    vaf: Optional[float]
    oncokb_level: Optional[str]


@strawberry.type
class StudyFrequencyType:
    study_id: str
    study_name: str
    cancer_type: Optional[str]
    mutation_count: int
    sample_count: int
    frequency_pct: Optional[float]


@strawberry.type
class CrossStudyFreqType:
    gene: str
    alteration: Optional[str]
    total_studies_with_alteration: int
    frequency_by_study: List[StudyFrequencyType]


@strawberry.type
class HotspotInfoType:
    residue: Optional[str]
    n_samples: Optional[int]
    cancer_types: Optional[List[str]]
    source: Optional[str]


@strawberry.type
class TopProteinChangeType:
    protein_change: str
    count: int
    is_hotspot: bool


@strawberry.type
class ClassificationCountType:
    classification: str
    count: int


@strawberry.type
class GeneSummaryType:
    gene: str
    total_mutations: int
    top_protein_changes: List[TopProteinChangeType]
    variant_classification_breakdown: List[ClassificationCountType]
    studies: List[StudyType]


@strawberry.type
class KmPointType:
    time: float
    survival: float
    n_at_risk: int
    n_events: int
    n_censored: int


@strawberry.type
class SurvivalCurvesType:
    gene: str
    protein_change: Optional[str]
    survival_type: str
    n_mutant: int
    n_wildtype: int
    log_rank_p: Optional[float]
    median_mutant_months: Optional[float]
    median_wildtype_months: Optional[float]
    mutant_curve: List[KmPointType]
    wildtype_curve: List[KmPointType]


@strawberry.type
class OncoPrintType:
    study_id: str
    genes: List[str]
    samples: List[str]
    sample_count: int
    gene_frequencies: strawberry.scalars.JSON
    alterations: strawberry.scalars.JSON


# ── Query ──────────────────────────────────────────────────────────────────────

@strawberry.type
class Query:

    @strawberry.field(description="List all public genomic studies.")
    async def studies(
        self,
        info: strawberry.types.Info,
        cancer_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[StudyType]:
        db = info.context["db"]
        from sqlalchemy import select
        from models.cohort import Study
        stmt = select(Study).where(Study.is_public.is_(True))  # noqa: E712
        if cancer_type:
            stmt = stmt.where(Study.cancer_type == cancer_type.upper())
        if source:
            stmt = stmt.where(Study.source == source)
        stmt = stmt.order_by(Study.sample_count.desc())
        rows = (await db.execute(stmt)).scalars().all()
        return [_study_to_gql(s) for s in rows]

    @strawberry.field(description="Mutations for a gene in a study.")
    async def study_mutations(
        self,
        info: strawberry.types.Info,
        study_id: str,
        gene: str,
        page: int = 1,
        per_page: int = 50,
    ) -> List[CohortMutationType]:
        db = info.context["db"]
        from sqlalchemy import select
        from models.cohort import CohortMutation, Study
        study = (await db.execute(
            select(Study).where(Study.study_id == study_id)
        )).scalar_one_or_none()
        if not study:
            return []
        stmt = (
            select(CohortMutation)
            .where(CohortMutation.study_id == study.id, CohortMutation.gene == gene.upper())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [_mutation_to_gql(m) for m in rows]

    @strawberry.field(description="Alteration frequency across all public studies.")
    async def cross_study_freq(
        self,
        info: strawberry.types.Info,
        gene: str,
        alteration: Optional[str] = None,
    ) -> CrossStudyFreqType:
        db = info.context["db"]
        from sqlalchemy import func, select
        from models.cohort import CohortMutation, Sample, Study
        gene_upper = gene.upper()
        stmt = (
            select(CohortMutation.study_id, func.count().label("n"))
            .where(CohortMutation.gene == gene_upper)
        )
        if alteration:
            stmt = stmt.where(CohortMutation.protein_change == alteration)
        stmt = stmt.group_by(CohortMutation.study_id)
        rows = (await db.execute(stmt)).all()

        study_ids = [r.study_id for r in rows]
        studies_by_id = {
            s.id: s
            for s in (await db.execute(select(Study).where(Study.id.in_(study_ids)))).scalars().all()
        }
        sample_counts = dict(
            (await db.execute(
                select(Sample.study_id, func.count().label("n"))
                .where(Sample.study_id.in_(study_ids))
                .group_by(Sample.study_id)
            )).all()
        )
        freq_list = []
        for row in rows:
            s = studies_by_id.get(row.study_id)
            if not s:
                continue
            ns = sample_counts.get(row.study_id, s.sample_count or 1)
            freq_list.append(StudyFrequencyType(
                study_id=s.study_id,
                study_name=s.name,
                cancer_type=s.cancer_type,
                mutation_count=row.n,
                sample_count=ns,
                frequency_pct=round(row.n / ns * 100, 2) if ns else None,
            ))
        return CrossStudyFreqType(
            gene=gene_upper,
            alteration=alteration,
            total_studies_with_alteration=len(freq_list),
            frequency_by_study=sorted(freq_list, key=lambda x: x.frequency_pct or 0, reverse=True),
        )

    @strawberry.field(description="Gene-level summary across all studies.")
    async def gene_summary(
        self,
        info: strawberry.types.Info,
        gene: str,
    ) -> GeneSummaryType:
        db = info.context["db"]
        from sqlalchemy import func, select
        from models.cohort import CohortMutation, Study
        from services.hotspot import get_hotspot_info
        gene_upper = gene.upper()
        top_changes = (await db.execute(
            select(CohortMutation.protein_change, func.count().label("n"))
            .where(CohortMutation.gene == gene_upper, CohortMutation.protein_change.isnot(None))
            .group_by(CohortMutation.protein_change)
            .order_by(func.count().desc())
            .limit(20)
        )).all()
        class_counts = (await db.execute(
            select(CohortMutation.variant_classification, func.count().label("n"))
            .where(CohortMutation.gene == gene_upper)
            .group_by(CohortMutation.variant_classification)
            .order_by(func.count().desc())
        )).all()
        study_ids = (await db.execute(
            select(func.distinct(CohortMutation.study_id)).where(CohortMutation.gene == gene_upper)
        )).scalars().all()
        studies = (await db.execute(select(Study).where(Study.id.in_(study_ids)))).scalars().all()
        return GeneSummaryType(
            gene=gene_upper,
            total_mutations=sum(r.n for r in top_changes),
            top_protein_changes=[
                TopProteinChangeType(
                    protein_change=r.protein_change,
                    count=r.n,
                    is_hotspot=get_hotspot_info(gene_upper, r.protein_change or "") is not None,
                )
                for r in top_changes
            ],
            variant_classification_breakdown=[
                ClassificationCountType(
                    classification=r.variant_classification or "Unknown",
                    count=r.n,
                )
                for r in class_counts
            ],
            studies=[_study_to_gql(s) for s in studies],
        )

    @strawberry.field(description="Kaplan-Meier survival curves for a gene in a study.")
    async def survival_curves(
        self,
        info: strawberry.types.Info,
        study_id: str,
        gene: str,
        alteration: Optional[str] = None,
        survival_type: str = "OS",
    ) -> SurvivalCurvesType:
        db = info.context["db"]
        from sqlalchemy import select
        from models.cohort import Study
        from services.survival import compute_survival_curves
        study = (await db.execute(select(Study).where(Study.study_id == study_id))).scalar_one_or_none()
        if not study:
            return SurvivalCurvesType(
                gene=gene, protein_change=alteration, survival_type=survival_type,
                n_mutant=0, n_wildtype=0, log_rank_p=None,
                median_mutant_months=None, median_wildtype_months=None,
                mutant_curve=[], wildtype_curve=[],
            )
        data = await compute_survival_curves(study.id, gene, alteration, db, survival_type)
        return SurvivalCurvesType(
            gene=data["gene"],
            protein_change=data.get("protein_change"),
            survival_type=data["survival_type"],
            n_mutant=data["n_mutant"],
            n_wildtype=data["n_wildtype"],
            log_rank_p=data.get("log_rank_p"),
            median_mutant_months=data.get("median_mutant_months"),
            median_wildtype_months=data.get("median_wildtype_months"),
            mutant_curve=[KmPointType(**p) for p in data["mutant_curve"]],
            wildtype_curve=[KmPointType(**p) for p in data["wildtype_curve"]],
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _study_to_gql(s) -> StudyType:
    return StudyType(
        study_id=s.study_id,
        name=s.name,
        cancer_type=s.cancer_type,
        cancer_type_label=s.cancer_type_label,
        sample_count=s.sample_count,
        reference_genome=s.reference_genome,
        pmid=s.pmid,
        source=s.source,
        data_types=s.data_types,
    )


def _mutation_to_gql(m) -> CohortMutationType:
    return CohortMutationType(
        gene=m.gene,
        protein_change=m.protein_change,
        hgvs_c=m.hgvs_c,
        variant_classification=m.variant_classification,
        chromosome=m.chromosome,
        position=m.position,
        ref_allele=m.ref_allele,
        alt_allele=m.alt_allele,
        vaf=m.vaf,
        oncokb_level=m.oncokb_level,
    )


# ── Schema + router ────────────────────────────────────────────────────────────

schema = strawberry.Schema(query=Query)


async def get_context(db=None):
    return {"db": db}


def create_graphql_router(db_dependency) -> GraphQLRouter:
    """Create the Strawberry GraphQL router with the DB session injected."""
    from fastapi import Depends

    async def context_getter(db=Depends(db_dependency)):
        return {"db": db}

    return GraphQLRouter(schema, context_getter=context_getter)
