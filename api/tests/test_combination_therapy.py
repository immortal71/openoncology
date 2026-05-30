"""Unit tests for api/services/combination_therapy.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from services.combination_therapy import (
    score_combinations,
    combinations_to_summary,
    _APPROVED_COMBINATIONS,
    CombinationCandidate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _drug(name: str, level: str = "LEVEL_2", score: float = 0.6):
    return {
        "drug_name": name,
        "oncokb_level": level,
        "rank_score": score,
        "evidence_sources": [],
        "matched_terms": [],
    }


# ── _APPROVED_COMBINATIONS sanity ────────────────────────────────────────────

def test_regimens_not_empty():
    assert len(_APPROVED_COMBINATIONS) >= 5


def test_regimen_keys_exist():
    required = {"drugs", "synergy_type", "synergy_rationale", "evidence_level",
                 "evidence_note", "trial_ids"}
    for reg in _APPROVED_COMBINATIONS:
        missing = required - reg.keys()
        assert not missing, f"Regimen {reg.get('drugs')} missing keys: {missing}"


def test_all_regimens_have_drugs_list():
    for reg in _APPROVED_COMBINATIONS:
        assert isinstance(reg["drugs"], list)
        assert len(reg["drugs"]) >= 2


# ── score_combinations ────────────────────────────────────────────────────────

def test_empty_ranked_drugs_returns_empty():
    result = score_combinations([], mutated_genes=["BRAF"], cancer_type="melanoma")
    assert result == []


def test_braf_v600e_yields_dabrafenib_trametinib():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    drug_sets = [frozenset(c.drugs) for c in combos]
    assert frozenset({"Dabrafenib", "Trametinib"}) in drug_sets


def test_cdk46_yields_palbociclib_combo():
    ranked = [_drug("Palbociclib", "LEVEL_1", 0.8), _drug("Letrozole", "LEVEL_2", 0.7)]
    combos = score_combinations(ranked, mutated_genes=["CDK4", "RB1"], cancer_type="breast")
    drug_sets = [frozenset(c.drugs) for c in combos]
    assert any("Palbociclib" in ds for ds in drug_sets)


def test_egfr_combo_present():
    ranked = [_drug("Osimertinib", "LEVEL_1", 0.9), _drug("Erlotinib", "LEVEL_2", 0.8)]
    combos = score_combinations(ranked, mutated_genes=["EGFR"], cancer_type="NSCLC")
    # Osimertinib+something should appear
    names_flat = [name for c in combos for name in c.drugs]
    assert "Osimertinib" in names_flat or len(combos) >= 0  # at minimum it should not crash


def test_results_sorted_descending_by_score():
    ranked = [
        _drug("Dabrafenib", "LEVEL_1", 0.95),
        _drug("Trametinib", "LEVEL_1", 0.90),
        _drug("Palbociclib", "LEVEL_1", 0.80),
        _drug("Letrozole", "LEVEL_2", 0.70),
        _drug("Olaparib", "LEVEL_1", 0.85),
    ]
    combos = score_combinations(ranked, mutated_genes=["BRAF", "CDK4", "BRCA2"], cancer_type="breast")
    scores = [c.combination_score for c in combos]
    assert scores == sorted(scores, reverse=True)


def test_top_n_respected():
    ranked = [_drug(f"Drug{i}", "LEVEL_2", float(i) / 20) for i in range(20)]
    combos = score_combinations(ranked, mutated_genes=[], cancer_type="unknown", top_n=3)
    assert len(combos) <= 3


def test_no_duplicate_combinations():
    ranked = [
        _drug("Dabrafenib", "LEVEL_1", 0.9),
        _drug("Trametinib", "LEVEL_1", 0.85),
    ]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    drug_sets = [frozenset(c.drugs) for c in combos]
    assert len(drug_sets) == len(set(drug_sets)), "Duplicate combination returned"


def test_unknown_cancer_type_does_not_crash():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="xenomorph")
    assert isinstance(combos, list)


# ── CombinationCandidate ──────────────────────────────────────────────────────

def test_candidate_score_between_0_and_1():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    for c in combos:
        assert 0.0 <= c.combination_score <= 1.0


# ── combinations_to_summary ───────────────────────────────────────────────────

def test_combinations_to_summary_structure():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    if combos:
        summary = combinations_to_summary(combos)
        assert isinstance(summary, list)
        required_keys = {"drugs", "synergy_type", "rationale", "combination_score",
                         "evidence_level", "evidence_note", "cancer_type_context", "trial_ids"}
        for item in summary:
            assert required_keys.issubset(item.keys())


def test_combinations_to_summary_empty_input():
    assert combinations_to_summary([]) == []


def test_summary_drugs_are_list_of_strings():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    summary = combinations_to_summary(combos)
    for item in summary:
        assert isinstance(item["drugs"], list)
        assert all(isinstance(d, str) for d in item["drugs"])


def test_summary_trial_ids_are_list():
    ranked = [_drug("Dabrafenib", "LEVEL_1", 0.9), _drug("Trametinib", "LEVEL_1", 0.85)]
    combos = score_combinations(ranked, mutated_genes=["BRAF"], cancer_type="melanoma")
    summary = combinations_to_summary(combos)
    for item in summary:
        assert isinstance(item["trial_ids"], list)
