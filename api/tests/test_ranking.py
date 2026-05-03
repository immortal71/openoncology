"""Tests for api/ai/ranking.py — drug scoring and ranking algorithm.

Covers:
  - compute_rank_score with all components present
  - compute_rank_score with missing components (weight redistribution)
  - compute_rank_score edge cases (all None, clamping)
  - rank_candidates returns list sorted descending by rank_score
  - _oncokb_score mapping
  - _phase_score mapping
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from api.ai.ranking import (
    compute_rank_score,
    rank_candidates,
    DrugScoreComponents,
    _oncokb_score,
    _phase_score,
    _normalize_oncokb_level,
)
from api.ai.ranking_config import RankingConfig, RobustnessConfig


# ── _oncokb_score ──────────────────────────────────────────────────────────────

class TestOncokbScore:
    def test_level_1_returns_max(self):
        assert _oncokb_score("LEVEL_1") == 1.0

    def test_level_1_case_insensitive(self):
        assert _oncokb_score("level_1") == 1.0

    def test_level_2(self):
        assert _oncokb_score("LEVEL_2") == 0.80

    def test_level_3a(self):
        assert _oncokb_score("LEVEL_3A") == 0.60

    def test_level_3b(self):
        assert _oncokb_score("LEVEL_3B") == 0.40

    def test_level_4(self):
        assert _oncokb_score("LEVEL_4") == 0.20

    def test_level_r1(self):
        assert _oncokb_score("LEVEL_R1") == 0.10

    def test_level_r2(self):
        assert _oncokb_score("LEVEL_R2") == 0.05

    def test_none_returns_none(self):
        assert _oncokb_score(None) is None

    def test_empty_string_returns_none(self):
        assert _oncokb_score("") is None

    def test_unknown_level_returns_none(self):
        assert _oncokb_score("LEVEL_X") is None


class TestNormalizeOncokbLevel:
    def test_numeric_level_normalized(self):
        assert _normalize_oncokb_level("2") == "LEVEL_2"

    def test_resistance_alias_normalized(self):
        assert _normalize_oncokb_level("r1") == "LEVEL_R1"

    def test_canonical_pass_through(self):
        assert _normalize_oncokb_level("LEVEL_3A") == "LEVEL_3A"


# ── _phase_score ──────────────────────────────────────────────────────────────

class TestPhaseScore:
    def test_approved_flag_returns_max(self):
        assert _phase_score(None, is_approved=True) == 1.0

    def test_phase_4_returns_max(self):
        assert _phase_score(4) == 1.0

    def test_phase_3(self):
        assert _phase_score(3) == 0.70

    def test_phase_2(self):
        assert _phase_score(2) == 0.50

    def test_phase_1(self):
        assert _phase_score(1) == 0.30

    def test_phase_0(self):
        assert _phase_score(0) == 0.10

    def test_phase_none_without_approved_returns_none(self):
        assert _phase_score(None) is None

    def test_approved_overrides_phase(self):
        # Even if phase=1, is_approved=True => 1.0
        assert _phase_score(1, is_approved=True) == 1.0


# ── compute_rank_score ────────────────────────────────────────────────────────

class TestComputeRankScore:
    def test_all_components_present_produces_value_in_range(self):
        components = DrugScoreComponents(
            binding_score=0.9,
            opentargets_score=0.8,
            oncokb_level="LEVEL_1",
            alphamissense_score=0.85,
            max_phase=4,
            is_approved=True,
        )
        score = compute_rank_score(components)
        assert 0.0 <= score <= 1.0

    def test_all_components_max_returns_one(self):
        components = DrugScoreComponents(
            binding_score=1.0,
            opentargets_score=1.0,
            oncokb_level="LEVEL_1",
            alphamissense_score=1.0,
            max_phase=4,
            is_approved=True,
        )
        score = compute_rank_score(components)
        assert score == 1.0

    def test_all_components_min_returns_near_zero(self):
        components = DrugScoreComponents(
            binding_score=0.0,
            opentargets_score=0.0,
            oncokb_level=None,
            alphamissense_score=0.0,
            max_phase=0,
            is_approved=False,
        )
        score = compute_rank_score(components)
        # phase_score(0) = 0.10, so not exactly 0
        assert 0.0 <= score <= 0.15

    def test_all_none_returns_zero(self):
        components = DrugScoreComponents()
        assert compute_rank_score(components) == 0.0

    def test_missing_binding_score_redistributes_weight(self):
        """Missing binding score (30%) should not prevent scoring.

        When binding is missing, the remaining components' weights are
        normalised to sum to 1.0.  The resulting score is determined solely
        by the non-binding components and must still fall in [0, 1].
        """
        without_binding = DrugScoreComponents(
            binding_score=None,
            opentargets_score=0.5,
            oncokb_level="LEVEL_1",
            alphamissense_score=0.5,
            max_phase=2,
        )
        score = compute_rank_score(without_binding)
        assert 0.0 <= score <= 1.0
        # Score must be positive (we have real components)
        assert score > 0.0

    def test_single_component_only_uses_that_score(self):
        components = DrugScoreComponents(opentargets_score=0.7)
        score = compute_rank_score(components)
        assert score == pytest.approx(0.546, abs=1e-4)

    def test_translational_bonus_rewards_convergent_oncokb_civic(self):
        with_bonus = DrugScoreComponents(
            oncokb_level="LEVEL_2",
            civic_score="B",
            opentargets_score=0.6,
        )
        without_bonus = DrugScoreComponents(
            oncokb_level="LEVEL_2",
            civic_score=None,
            opentargets_score=0.6,
        )
        assert compute_rank_score(with_bonus) > compute_rank_score(without_bonus)

    def test_higher_variance_penalty_lowers_same_candidate_score(self):
        components = DrugScoreComponents(
            binding_score=1.0,
            opentargets_score=0.0,
            oncokb_level="LEVEL_4",
            alphamissense_score=0.0,
            max_phase=0,
            civic_score="E",
        )
        baseline_cfg = RankingConfig()
        strict_cfg = RankingConfig(
            robustness=RobustnessConfig(
                variance_penalty_factor=0.5,
                max_variance_penalty=0.3,
                translational_bonus_factor=baseline_cfg.robustness.translational_bonus_factor,
                max_translational_bonus=baseline_cfg.robustness.max_translational_bonus,
                multi_source_bonus_per_source=baseline_cfg.robustness.multi_source_bonus_per_source,
                multi_source_bonus_cap=baseline_cfg.robustness.multi_source_bonus_cap,
            )
        )
        assert compute_rank_score(components, strict_cfg) < compute_rank_score(components, baseline_cfg)

    def test_result_is_clamped_to_one(self):
        """No component combination should produce score > 1."""
        components = DrugScoreComponents(
            binding_score=1.0,
            opentargets_score=1.0,
            oncokb_level="LEVEL_1",
            alphamissense_score=1.0,
            is_approved=True,
        )
        assert compute_rank_score(components) <= 1.0

    def test_result_is_clamped_to_zero(self):
        """No combination should produce score < 0."""
        components = DrugScoreComponents(
            binding_score=0.0,
            opentargets_score=0.0,
            alphamissense_score=0.0,
        )
        assert compute_rank_score(components) >= 0.0

    def test_approved_drug_scores_higher_than_phase_1(self):
        approved = DrugScoreComponents(is_approved=True, opentargets_score=0.5)
        phase1 = DrugScoreComponents(max_phase=1, opentargets_score=0.5)
        assert compute_rank_score(approved) > compute_rank_score(phase1)

    def test_higher_oncokb_level_scores_higher(self):
        l1 = DrugScoreComponents(oncokb_level="LEVEL_1", opentargets_score=0.5)
        l4 = DrugScoreComponents(oncokb_level="LEVEL_4", opentargets_score=0.5)
        assert compute_rank_score(l1) > compute_rank_score(l4)

    def test_score_is_rounded_to_4_decimal_places(self):
        components = DrugScoreComponents(opentargets_score=1 / 3)
        score = compute_rank_score(components)
        # Should be rounded to 4 decimal places
        assert score == round(score, 4)


# ── rank_candidates ───────────────────────────────────────────────────────────

class TestRankCandidates:
    def test_sorted_descending_by_rank_score(self):
        candidates = [
            {"drug_name": "DrugA", "opentargets_score": 0.3},
            {"drug_name": "DrugB", "opentargets_score": 0.9},
            {"drug_name": "DrugC", "opentargets_score": 0.6},
        ]
        ranked = rank_candidates(candidates)
        scores = [c["rank_score"] for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_score_attached_to_each_candidate(self):
        candidates = [{"drug_name": "X", "opentargets_score": 0.5}]
        ranked = rank_candidates(candidates)
        assert "rank_score" in ranked[0]

    def test_empty_list_returns_empty(self):
        assert rank_candidates([]) == []

    def test_single_candidate_returned_unchanged_structure(self):
        candidates = [{"drug_name": "Solo", "max_phase": 2}]
        ranked = rank_candidates(candidates)
        assert len(ranked) == 1
        assert ranked[0]["drug_name"] == "Solo"
        assert "rank_score" in ranked[0]

    def test_approved_drug_ranks_first_when_other_scores_equal(self):
        """An approved drug (phase score 1.0) should beat a phase-1 drug
        when all other evidence signals are equal."""
        candidates = [
            {"drug_name": "Phase1",  "max_phase": 1,  "opentargets_score": 0.5},
            {"drug_name": "Approved", "is_approved": True, "opentargets_score": 0.5},
        ]
        ranked = rank_candidates(candidates)
        assert ranked[0]["drug_name"] == "Approved"

    def test_candidates_with_no_scores_get_zero_rank(self):
        candidates = [{"drug_name": "Mystery"}]
        ranked = rank_candidates(candidates)
        assert ranked[0]["rank_score"] == 0.0

    def test_phase_key_alias_supported(self):
        """rank_candidates should accept 'phase' as fallback for 'max_phase'."""
        candidates = [{"drug_name": "D", "phase": 3}]
        ranked = rank_candidates(candidates)
        assert ranked[0]["rank_score"] > 0.0

    def test_is_approved_bool_coercion(self):
        """Truthy non-bool values for is_approved should be handled."""
        candidates = [{"drug_name": "D", "is_approved": 1}]
        ranked = rank_candidates(candidates)
        assert ranked[0]["rank_score"] > 0.0

    def test_rank_candidates_auto_applies_co_mutation_penalty(self):
        candidates = [
            {
                "drug_name": "EGFR Drug",
                "target_gene": "EGFR",
                "co_mutated_genes": ["MET"],
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.7,
            },
            {
                "drug_name": "EGFR Drug NoCoMut",
                "target_gene": "EGFR",
                "co_mutated_genes": [],
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.7,
            },
        ]
        ranked = rank_candidates(candidates)
        by_name = {c["drug_name"]: c for c in ranked}
        assert by_name["EGFR Drug"]["co_mutation_penalty"] > 0.0
        assert by_name["EGFR Drug"]["rank_score"] < by_name["EGFR Drug NoCoMut"]["rank_score"]

    def test_near_tie_prefers_configured_modern_soc(self):
        candidates = [
            {
                "drug_name": "Erlotinib",
                "target_gene": "EGFR",
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.65,
                "max_phase": 4,
            },
            {
                "drug_name": "Osimertinib",
                "target_gene": "EGFR",
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.65,
                "max_phase": 4,
            },
        ]
        ranked = rank_candidates(candidates)
        assert ranked[0]["drug_name"] == "Osimertinib"
        assert ranked[0].get("clinical_priority_boost", 0.0) > 0.0

    def test_far_apart_scores_ignore_tie_breaker_boost(self):
        candidates = [
            {
                "drug_name": "Osimertinib",
                "target_gene": "EGFR",
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.30,
                "max_phase": 2,
            },
            {
                "drug_name": "Gefitinib",
                "target_gene": "EGFR",
                "oncokb_level": "LEVEL_2",
                "opentargets_score": 0.90,
                "max_phase": 4,
            },
        ]
        ranked = rank_candidates(candidates)
        assert ranked[0]["drug_name"] == "Gefitinib"
