"""Integration tests for api/routes/cohorts.py

Uses the in-memory SQLite fixtures from conftest.py — no database connection
needed.  Each test seeds the minimal rows required, then exercises the
cohort-browser endpoints via the AsyncClient fixture.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from httpx import AsyncClient

from models.cohort import Study, Sample, CohortMutation


# ── Seed helpers ──────────────────────────────────────────────────────────────

def _study(study_id="tcga_luad", name="TCGA LUAD", cancer_type="LUAD",
           source="TCGA", sample_count=100):
    return Study(
        study_id=study_id,
        name=name,
        cancer_type=cancer_type,
        cancer_type_label="Lung Adenocarcinoma",
        sample_count=sample_count,
        data_types=["SNV", "CNA"],
        reference_genome="GRCh38",
        pmid="12345678",
        source=source,
        is_public=True,
    )


def _sample(study_id_fk: str, sample_id: str = "SAMPLE-001"):
    return Sample(study_id=study_id_fk, sample_id=sample_id)


def _mutation(study_id_fk: str, sample_id_fk: str, gene: str = "KRAS",
               protein_change: str = "p.G12D",
               variant_classification: str = "Missense_Mutation"):
    return CohortMutation(
        study_id=study_id_fk,
        sample_id=sample_id_fk,
        gene=gene,
        protein_change=protein_change,
        variant_classification=variant_classification,
    )


# ── GET /api/cohorts/studies ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_studies_returns_list(client: AsyncClient, db_session):
    db_session.add(_study())
    await db_session.commit()

    resp = await client.get("/api/cohorts/studies")
    assert resp.status_code == 200
    body = resp.json()
    assert "studies" in body
    assert body["total"] >= 1
    assert any(s["study_id"] == "tcga_luad" for s in body["studies"])


@pytest.mark.asyncio
async def test_list_studies_empty(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/studies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["studies"] == []


@pytest.mark.asyncio
async def test_list_studies_filter_cancer_type(client: AsyncClient, db_session):
    db_session.add(_study(study_id="tcga_luad", cancer_type="LUAD"))
    db_session.add(_study(study_id="tcga_brca", name="TCGA BRCA", cancer_type="BRCA",
                           source="TCGA", sample_count=80))
    await db_session.commit()

    resp = await client.get("/api/cohorts/studies?cancer_type=LUAD")
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(s["cancer_type"] == "LUAD" for s in studies)
    assert not any(s["study_id"] == "tcga_brca" for s in studies)


@pytest.mark.asyncio
async def test_list_studies_filter_source(client: AsyncClient, db_session):
    db_session.add(_study(study_id="tcga_luad", source="TCGA"))
    db_session.add(_study(study_id="icgc_luad", name="ICGC LUAD", source="ICGC",
                           cancer_type="LUAD", sample_count=50))
    await db_session.commit()

    resp = await client.get("/api/cohorts/studies?source=TCGA")
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(s["source"] == "TCGA" for s in studies)
    assert not any(s["study_id"] == "icgc_luad" for s in studies)


# ── GET /api/cohorts/studies/{study_id} ──────────────────────────────────────

@pytest.mark.asyncio
async def test_get_study_detail(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    db_session.add(_mutation(study.id, sample.id, gene="KRAS"))
    db_session.add(_mutation(study.id, sample.id, gene="TP53"))
    await db_session.commit()

    resp = await client.get("/api/cohorts/studies/tcga_luad")
    assert resp.status_code == 200
    body = resp.json()
    assert body["study_id"] == "tcga_luad"
    assert "sample_count_live" in body
    assert body["sample_count_live"] == 1
    assert "distinct_genes_mutated" in body
    assert body["distinct_genes_mutated"] == 2


@pytest.mark.asyncio
async def test_get_study_404(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/studies/nonexistent_study_xyz")
    assert resp.status_code == 404


# ── GET /api/cohorts/{study_id}/mutations ─────────────────────────────────────

@pytest.mark.asyncio
async def test_get_mutations_returns_list(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    for gene in ["KRAS", "TP53", "EGFR"]:
        db_session.add(_mutation(study.id, sample.id, gene=gene))
    await db_session.commit()

    resp = await client.get("/api/cohorts/tcga_luad/mutations")
    assert resp.status_code == 200
    body = resp.json()
    assert "mutations" in body
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_get_mutations_gene_filter(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    db_session.add(_mutation(study.id, sample.id, gene="KRAS"))
    db_session.add(_mutation(study.id, sample.id, gene="TP53"))
    await db_session.commit()

    resp = await client.get("/api/cohorts/tcga_luad/mutations?gene=KRAS")
    assert resp.status_code == 200
    body = resp.json()
    assert all(m["gene"] == "KRAS" for m in body["mutations"])
    assert body["gene_filter"] == "KRAS"


@pytest.mark.asyncio
async def test_get_mutations_pagination(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    for i in range(10):
        db_session.add(_mutation(study.id, sample.id, gene=f"GENE{i}"))
    await db_session.commit()

    resp = await client.get("/api/cohorts/tcga_luad/mutations?page=1&per_page=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["per_page"] == 3
    assert len(body["mutations"]) == 3
    assert body["total"] == 10


@pytest.mark.asyncio
async def test_get_mutations_study_404(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/no_such_study/mutations")
    assert resp.status_code == 404


# ── GET /api/cohorts/cross-study ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_study_missing_gene_returns_422(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/cross-study")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cross_study_returns_frequency(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    db_session.add(_mutation(study.id, sample.id, gene="EGFR", protein_change="p.L858R"))
    await db_session.commit()

    resp = await client.get("/api/cohorts/cross-study?gene=EGFR")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gene"] == "EGFR"
    assert "frequency_by_study" in body
    assert body["total_studies_with_alteration"] >= 1
    assert any(s["study_id"] == "tcga_luad" for s in body["frequency_by_study"])


@pytest.mark.asyncio
async def test_cross_study_no_hits(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/cross-study?gene=FAKEGENE99")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_studies_with_alteration"] == 0
    assert body["frequency_by_study"] == []


# ── GET /api/cohorts/oncoprint ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_oncoprint_returns_matrix(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    s1 = _sample(study.id, sample_id="S1")
    s2 = _sample(study.id, sample_id="S2")
    db_session.add(s1)
    db_session.add(s2)
    await db_session.flush()

    db_session.add(_mutation(study.id, s1.id, gene="KRAS"))
    db_session.add(_mutation(study.id, s2.id, gene="TP53"))
    await db_session.commit()

    resp = await client.get("/api/cohorts/oncoprint?study_id=tcga_luad&genes=KRAS,TP53")
    assert resp.status_code == 200
    body = resp.json()
    assert body["study_id"] == "tcga_luad"
    assert "KRAS" in body["genes"]
    assert "TP53" in body["genes"]
    assert "alterations" in body
    assert "gene_frequencies" in body


@pytest.mark.asyncio
async def test_oncoprint_no_genes_returns_422(client: AsyncClient, db_session):
    # Study must exist so the genes validation check runs (not a 404)
    db_session.add(_study())
    await db_session.commit()
    resp = await client.get("/api/cohorts/oncoprint?study_id=tcga_luad&genes=")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_oncoprint_study_404(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/oncoprint?study_id=no_such&genes=KRAS")
    assert resp.status_code == 404


# ── GET /api/cohorts/gene-summary ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gene_summary_returns_top_changes(client: AsyncClient, db_session):
    study = _study()
    db_session.add(study)
    await db_session.flush()

    sample = _sample(study.id)
    db_session.add(sample)
    await db_session.flush()

    for pc in ["p.G12D", "p.G12D", "p.G12V", "p.G12C"]:
        db_session.add(_mutation(study.id, sample.id, gene="KRAS", protein_change=pc))
    await db_session.commit()

    resp = await client.get("/api/cohorts/gene-summary?gene=KRAS")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gene"] == "KRAS"
    assert "top_protein_changes" in body
    assert len(body["top_protein_changes"]) > 0
    # p.G12D appears twice — should be first
    top = body["top_protein_changes"][0]
    assert top["protein_change"] == "p.G12D"
    assert top["count"] == 2
    assert "is_hotspot" in top


@pytest.mark.asyncio
async def test_gene_summary_missing_gene_returns_422(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/gene-summary")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_gene_summary_no_data_empty_lists(client: AsyncClient, db_session):
    resp = await client.get("/api/cohorts/gene-summary?gene=NOVELGENE123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gene"] == "NOVELGENE123"
    assert body["top_protein_changes"] == []
    assert body["studies"] == []
