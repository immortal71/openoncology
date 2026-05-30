"""Unit tests for api/services/immunotherapy_biomarkers.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from services.immunotherapy_biomarkers import (
    compute_immunotherapy_profile,
    get_immunotherapy_candidates,
    immunotherapy_candidates_to_drug_dicts,
    TMB_HIGH_CUTOFF,
    MMR_GENES,
    HRD_GENES,
    POLE_GENES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _snv(gene="TP53", mutation_type="missense_variant"):
    return {"gene": gene, "mutation_type": mutation_type, "ref": "C", "alt": "T"}


def _lof(gene):
    """Loss-of-function mutation (frameshift) for a given gene."""
    return {"gene": gene, "mutation_type": "frameshift_variant", "ref": "C", "alt": ""}


def _make_mutations(n: int, gene="TP53"):
    return [_snv(gene) for _ in range(n)]


# ── TMB computation ───────────────────────────────────────────────────────────

def test_tmb_below_cutoff():
    muts = _make_mutations(200)   # 200/38 ≈ 5.3 mut/Mb → low
    profile = compute_immunotherapy_profile(muts)
    assert profile.tmb_mutations_per_mb == pytest.approx(200 / 38.0, rel=0.01)
    assert profile.tmb_status == "TMB-L"


def test_tmb_above_cutoff():
    muts = _make_mutations(400)   # 400/38 ≈ 10.5 mut/Mb → high
    profile = compute_immunotherapy_profile(muts)
    assert profile.tmb_status == "TMB-H"


def test_tmb_custom_genome_size():
    muts = _make_mutations(10)
    profile = compute_immunotherapy_profile(muts, genome_mb=1.0)
    assert profile.tmb_mutations_per_mb == pytest.approx(10.0, rel=0.01)


def test_tmb_exactly_at_cutoff():
    n = round(TMB_HIGH_CUTOFF * 38.0)
    muts = _make_mutations(n)
    profile = compute_immunotherapy_profile(muts)
    assert profile.tmb_status == "TMB-H"


# ── MSI / MMR detection ───────────────────────────────────────────────────────

def test_msi_detected_via_mmr_gene():
    # Frameshift (LOF) in MLH1 → MSI-H proxy
    muts = [_lof("MLH1")] * 5 + _make_mutations(50)
    profile = compute_immunotherapy_profile(muts)
    assert profile.msi_status == "MSI-H"
    assert "MLH1" in profile.mmr_gene_hits


def test_no_msi_without_mmr_gene():
    muts = _make_mutations(50)
    profile = compute_immunotherapy_profile(muts)
    assert profile.msi_status == "MSS"
    assert profile.mmr_gene_hits == []


def test_all_mmr_genes_detected():
    for gene in MMR_GENES:
        muts = [_lof(gene)] + _make_mutations(20)
        profile = compute_immunotherapy_profile(muts)
        assert profile.msi_status == "MSI-H", f"MMR gene {gene} not detected"


# ── HRD detection ─────────────────────────────────────────────────────────────

def test_hrd_detected_via_brca1():
    muts = [_lof("BRCA1")] * 3 + _make_mutations(30)
    profile = compute_immunotherapy_profile(muts)
    assert profile.hrd_status == "HRD"
    assert "BRCA1" in profile.hrd_gene_hits


def test_hrd_not_detected_without_hrd_gene():
    muts = _make_mutations(30)
    profile = compute_immunotherapy_profile(muts)
    assert profile.hrd_status == "NOT_HRD"


# ── POLE detection ────────────────────────────────────────────────────────────

def test_pole_detected():
    muts = [_snv(gene="POLE")] + _make_mutations(10)
    profile = compute_immunotherapy_profile(muts)
    assert profile.pole_mutated is True


# ── Candidate generation ──────────────────────────────────────────────────────

def test_no_candidates_for_empty_profile():
    muts = _make_mutations(5)  # low TMB, no special genes
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="NSCLC")
    assert candidates == []


def test_tmb_high_yields_checkpoint_inhibitors():
    muts = _make_mutations(500)   # very high TMB
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="NSCLC")
    drug_names = {c.drug_name for c in candidates}
    assert "Pembrolizumab" in drug_names


def test_msi_high_yields_checkpoint():
    muts = [_lof("MLH1")] * 5 + _make_mutations(50)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="colorectal")
    drug_names = {c.drug_name for c in candidates}
    assert "Dostarlimab" in drug_names or "Pembrolizumab" in drug_names


def test_hrd_yields_parp_inhibitor():
    muts = [_lof("BRCA2")] * 3 + _make_mutations(20)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="ovarian")
    drug_names = {c.drug_name for c in candidates}
    assert "Olaparib" in drug_names


def test_candidates_sorted_by_rank_score():
    muts = [_lof("BRCA1")] * 3 + [_lof("MLH1")] * 3 + _make_mutations(400)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="endometrial")
    scores = [c.rank_score_estimate for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_candidates_deduplicated():
    muts = [_lof("BRCA1")] * 3 + _make_mutations(400)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, cancer_type="breast")
    drug_names = [c.drug_name for c in candidates]
    assert len(drug_names) == len(set(drug_names)), "Duplicate drug names in candidates"


# ── to_drug_dicts ──────────────────────────────────────────────────────────────

def test_immunotherapy_candidates_to_drug_dicts_structure():
    muts = _make_mutations(500)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, "NSCLC")
    dicts = immunotherapy_candidates_to_drug_dicts(candidates)
    assert isinstance(dicts, list)
    for d in dicts:
        assert "drug_name" in d
        assert "oncokb_level" in d
        assert "evidence_sources" in d
        assert isinstance(d["evidence_sources"], list)


def test_immunotherapy_drug_dicts_rank_compatible():
    """All dict keys must be compatible with rank_candidates() input format."""
    muts = _make_mutations(500)
    profile = compute_immunotherapy_profile(muts)
    candidates = get_immunotherapy_candidates(profile, "NSCLC")
    dicts = immunotherapy_candidates_to_drug_dicts(candidates)
    required_keys = {"drug_name", "oncokb_level", "is_approved", "max_phase",
                     "binding_score", "opentargets_score", "evidence_sources", "matched_terms"}
    for d in dicts:
        assert required_keys.issubset(d.keys()), f"Missing keys in dict: {d}"
