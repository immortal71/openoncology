"""Unit tests for the private scoring helper functions in services/drug_discovery.py.

These functions score drug-like properties (oral exposure, toxicity risk,
synthesis feasibility) using Lipinski / ADMET heuristics derived from
molecular descriptors.  They have no I/O dependencies, so every test runs
entirely in-process.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from services.drug_discovery import (
    _score_oral_exposure,
    _score_toxicity_risk,
    _score_synthesis_feasibility,
    _score_design_priority,
    _weighted_mean,
    _mutation_complexity_modifier,
    _fallback_fragments,
    _extract_components,
    _clamp,
    _to_float,
    _phase_rank,
)


# ─────────────────────────────────────────────────────────────────────────────
# _clamp
# ─────────────────────────────────────────────────────────────────────────────

class TestClamp:
    def test_value_in_range_unchanged(self):
        assert _clamp(0.5) == 0.5

    def test_value_above_upper_clamped(self):
        assert _clamp(1.5) == 1.0

    def test_value_below_lower_clamped(self):
        assert _clamp(-0.1) == 0.0

    def test_custom_bounds(self):
        assert _clamp(10.0, 0.0, 5.0) == 5.0
        assert _clamp(-1.0, 0.0, 5.0) == 0.0
        assert _clamp(3.0, 0.0, 5.0) == 3.0


# ─────────────────────────────────────────────────────────────────────────────
# _to_float
# ─────────────────────────────────────────────────────────────────────────────

class TestToFloat:
    def test_none_returns_none(self):
        assert _to_float(None) is None

    def test_empty_string_returns_none(self):
        assert _to_float("") is None

    def test_int_converts(self):
        assert _to_float(5) == 5.0

    def test_string_float_converts(self):
        assert _to_float("3.14") == pytest.approx(3.14)

    def test_non_numeric_returns_none(self):
        assert _to_float("abc") is None


# ─────────────────────────────────────────────────────────────────────────────
# _phase_rank
# ─────────────────────────────────────────────────────────────────────────────

class TestPhaseRank:
    def test_approval_returns_4(self):
        assert _phase_rank("APPROVAL") == 4

    def test_phase4_returns_4(self):
        assert _phase_rank("PHASE4") == 4

    def test_phase3_returns_3(self):
        assert _phase_rank("PHASE3") == 3

    def test_phase2_returns_2(self):
        assert _phase_rank("PHASE2") == 2

    def test_phase1_returns_1(self):
        assert _phase_rank("PHASE1") == 1

    def test_integer_phase_passthrough(self):
        assert _phase_rank(3) == 3

    def test_unknown_label_returns_0(self):
        assert _phase_rank("PRECLINICAL") == 0

    def test_none_returns_0(self):
        assert _phase_rank(None) == 0


# ─────────────────────────────────────────────────────────────────────────────
# _score_oral_exposure
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreOralExposure:
    # Aspirin-like reference molecule — should score near maximum
    _GOOD_MOLECULE = {
        "molecular_weight": 350.0,
        "alogp": 2.5,
        "psa": 80.0,
        "hba": 4,
        "hbd": 2,
        "ro5_pass": True,
    }

    def test_all_none_returns_none(self):
        assert _score_oral_exposure({}) is None

    def test_single_field_not_none_returns_score(self):
        score = _score_oral_exposure({"molecular_weight": 300.0})
        assert score is not None

    def test_drug_like_molecule_scores_high(self):
        score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert score is not None
        assert score >= 80.0

    def test_high_mw_penalises_score(self):
        heavy = {**self._GOOD_MOLECULE, "molecular_weight": 600.0}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        heavy_score = _score_oral_exposure(heavy)
        assert heavy_score < good_score

    def test_low_mw_penalises_score(self):
        tiny = {**self._GOOD_MOLECULE, "molecular_weight": 100.0}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        tiny_score = _score_oral_exposure(tiny)
        assert tiny_score < good_score

    def test_high_alogp_penalises_score(self):
        lipophilic = {**self._GOOD_MOLECULE, "alogp": 6.0}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(lipophilic) < good_score

    def test_low_alogp_penalises_score(self):
        hydrophilic = {**self._GOOD_MOLECULE, "alogp": 0.0}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(hydrophilic) < good_score

    def test_high_psa_penalises_score(self):
        polar = {**self._GOOD_MOLECULE, "psa": 160.0}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(polar) < good_score

    def test_high_hba_penalises_score(self):
        hba_heavy = {**self._GOOD_MOLECULE, "hba": 12}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(hba_heavy) < good_score

    def test_high_hbd_penalises_score(self):
        hbd_heavy = {**self._GOOD_MOLECULE, "hbd": 7}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(hbd_heavy) < good_score

    def test_ro5_fail_penalises_score(self):
        ro5_fail = {**self._GOOD_MOLECULE, "ro5_pass": False}
        good_score = _score_oral_exposure(self._GOOD_MOLECULE)
        assert _score_oral_exposure(ro5_fail) < good_score

    def test_score_bounded_0_to_100(self):
        # Worst-case molecule (all violations) should be clamped ≥ 0
        worst = {
            "molecular_weight": 1000.0,
            "alogp": 10.0,
            "psa": 200.0,
            "hba": 20,
            "hbd": 15,
            "ro5_pass": False,
        }
        score = _score_oral_exposure(worst)
        assert score is not None
        assert 0.0 <= score <= 100.0


# ─────────────────────────────────────────────────────────────────────────────
# _score_toxicity_risk
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreToxicityRisk:
    _CLEAN_MOLECULE = {
        "molecular_weight": 300.0,
        "alogp": 2.0,
        "psa": 90.0,
        "rtb": 4,
        "ro5_pass": True,
    }

    def test_all_none_returns_none(self):
        assert _score_toxicity_risk({}) is None

    def test_single_field_not_none_returns_score(self):
        assert _score_toxicity_risk({"molecular_weight": 300.0}) is not None

    def test_clean_molecule_baseline_risk(self):
        # Baseline risk is 0.20 → 20.0% without any penalties
        score = _score_toxicity_risk(self._CLEAN_MOLECULE)
        assert score is not None
        assert score == pytest.approx(20.0)

    def test_high_mw_increases_risk(self):
        heavy = {**self._CLEAN_MOLECULE, "molecular_weight": 600.0}
        assert _score_toxicity_risk(heavy) > _score_toxicity_risk(self._CLEAN_MOLECULE)

    def test_high_alogp_increases_risk(self):
        lipophilic = {**self._CLEAN_MOLECULE, "alogp": 5.0}
        assert _score_toxicity_risk(lipophilic) > _score_toxicity_risk(self._CLEAN_MOLECULE)

    def test_low_psa_increases_risk(self):
        nonpolar = {**self._CLEAN_MOLECULE, "psa": 10.0}
        assert _score_toxicity_risk(nonpolar) > _score_toxicity_risk(self._CLEAN_MOLECULE)

    def test_high_rtb_increases_risk(self):
        flexible = {**self._CLEAN_MOLECULE, "rtb": 12}
        assert _score_toxicity_risk(flexible) > _score_toxicity_risk(self._CLEAN_MOLECULE)

    def test_ro5_fail_increases_risk(self):
        ro5_fail = {**self._CLEAN_MOLECULE, "ro5_pass": False}
        assert _score_toxicity_risk(ro5_fail) > _score_toxicity_risk(self._CLEAN_MOLECULE)

    def test_score_bounded_0_to_100(self):
        worst = {
            "molecular_weight": 800.0,
            "alogp": 6.0,
            "psa": 5.0,
            "rtb": 15,
            "ro5_pass": False,
        }
        score = _score_toxicity_risk(worst)
        assert score is not None
        assert 0.0 <= score <= 100.0


# ─────────────────────────────────────────────────────────────────────────────
# _score_synthesis_feasibility
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreSynthesisFeasibility:
    _EASY_MOLECULE = {
        "molecular_weight": 280.0,
        "rtb": 3,
        "hba": 4,
        "hbd": 1,
    }

    def test_all_none_returns_none(self):
        assert _score_synthesis_feasibility({}) is None

    def test_single_field_returns_score(self):
        assert _score_synthesis_feasibility({"molecular_weight": 280.0}) is not None

    def test_simple_molecule_scores_high(self):
        score = _score_synthesis_feasibility(self._EASY_MOLECULE)
        assert score is not None
        assert score >= 70.0

    def test_high_mw_penalises_feasibility(self):
        heavy = {**self._EASY_MOLECULE, "molecular_weight": 600.0}
        assert _score_synthesis_feasibility(heavy) < _score_synthesis_feasibility(self._EASY_MOLECULE)

    def test_high_rtb_penalises_feasibility(self):
        flexible = {**self._EASY_MOLECULE, "rtb": 12}
        assert _score_synthesis_feasibility(flexible) < _score_synthesis_feasibility(self._EASY_MOLECULE)

    def test_high_hba_penalises_feasibility(self):
        hba_heavy = {**self._EASY_MOLECULE, "hba": 12}
        assert _score_synthesis_feasibility(hba_heavy) < _score_synthesis_feasibility(self._EASY_MOLECULE)

    def test_high_hbd_penalises_feasibility(self):
        hbd_heavy = {**self._EASY_MOLECULE, "hbd": 6}
        assert _score_synthesis_feasibility(hbd_heavy) < _score_synthesis_feasibility(self._EASY_MOLECULE)

    def test_score_bounded_0_to_100(self):
        worst = {
            "molecular_weight": 900.0,
            "rtb": 20,
            "hba": 15,
            "hbd": 10,
        }
        score = _score_synthesis_feasibility(worst)
        assert score is not None
        assert 0.0 <= score <= 100.0


# ─────────────────────────────────────────────────────────────────────────────
# _weighted_mean
# ─────────────────────────────────────────────────────────────────────────────

class TestWeightedMean:
    def test_all_none_returns_none(self):
        assert _weighted_mean([(None, 0.5), (None, 0.5)]) is None

    def test_empty_list_returns_none(self):
        assert _weighted_mean([]) is None

    def test_single_component(self):
        result = _weighted_mean([(0.7, 1.0)])
        assert result == pytest.approx(0.7, abs=0.001)

    def test_equal_weights_averages(self):
        result = _weighted_mean([(0.4, 0.5), (0.8, 0.5)])
        assert result == pytest.approx(0.6, abs=0.001)

    def test_unequal_weights_biased(self):
        result = _weighted_mean([(1.0, 0.9), (0.0, 0.1)])
        assert result == pytest.approx(0.9, abs=0.001)

    def test_none_component_skipped_and_weight_renormalised(self):
        # Only the 0.8 component remains; its weight becomes 100%
        result = _weighted_mean([(None, 0.5), (0.8, 0.5)])
        assert result == pytest.approx(0.8, abs=0.001)

    def test_output_clamped_to_unit_interval(self):
        # Weights can produce values > 1 before clamping
        result = _weighted_mean([(2.0, 1.0)])
        assert 0.0 <= result <= 1.0

    def test_zero_weights_with_none_returns_none(self):
        assert _weighted_mean([(None, 0.0)]) is None


# ─────────────────────────────────────────────────────────────────────────────
# _mutation_complexity_modifier
# ─────────────────────────────────────────────────────────────────────────────

class TestMutationComplexityModifier:
    def test_empty_list_returns_zero(self):
        assert _mutation_complexity_modifier([]) == 0.0

    def test_no_hotspot_single_mutation_breadth_only(self):
        result = _mutation_complexity_modifier(["p.A100G"])
        # breadth_bonus = 1 * 0.03 = 0.03, no hotspot bonus
        assert result == pytest.approx(0.03, abs=0.001)

    def test_known_hotspot_g12_adds_bonus(self):
        result = _mutation_complexity_modifier(["p.G12D"])
        # breadth=0.03 + hotspot=0.05 = 0.08
        assert result == pytest.approx(0.08, abs=0.001)

    def test_known_hotspot_v600_adds_bonus(self):
        result = _mutation_complexity_modifier(["p.V600E"])
        assert result == pytest.approx(0.08, abs=0.001)

    def test_multiple_hotspots_accumulate(self):
        result = _mutation_complexity_modifier([
            "p.G12D",
            "p.V600E",
            "p.L858R",
            "p.R175H",
        ])
        # breadth = min(4, 6) * 0.03 = 0.12, hotspots = min(3,4) * 0.05 = 0.15, but 0.12+0.15=0.27 clamped to 0.25
        assert result == pytest.approx(0.25, abs=0.001)

    def test_output_capped_at_0_25(self):
        # Force worst-case: 6 mutations, 4 hotspots → 0.18 + 0.20 = 0.38, clamped to 0.25
        mutations = [
            "p.G12D", "p.V600E", "p.L858R", "p.R175H",
            "p.T790M", "p.Y220C",
        ]
        result = _mutation_complexity_modifier(mutations)
        assert result == pytest.approx(0.25, abs=0.001)

    def test_breadth_bonus_capped_at_6_mutations(self):
        many_benign = [f"p.A{i}G" for i in range(10)]
        result = _mutation_complexity_modifier(many_benign)
        # breadth_bonus capped: min(10, 6) * 0.03 = 0.18
        assert result == pytest.approx(0.18, abs=0.001)


# ─────────────────────────────────────────────────────────────────────────────
# _fallback_fragments
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackFragments:
    def test_simple_smiles_returns_list(self):
        result = _fallback_fragments("CCO")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_empty_smiles_returns_empty(self):
        assert _fallback_fragments("") == []

    def test_no_duplicates_in_output(self):
        result = _fallback_fragments("CC.CC.CC")
        assert len(result) == len(set(result))

    def test_max_24_fragments(self):
        # A contrived long SMILES should not produce more than 24 fragments
        long_smiles = ".".join([f"C{i}" for i in range(50)])
        result = _fallback_fragments(long_smiles)
        assert len(result) <= 24

    def test_aromatic_ring_split_on_brackets(self):
        result = _fallback_fragments("c1ccccc1[OH]")
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# _extract_components (RDKit optional path)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractComponents:
    def test_returns_scaffolds_and_fragments_keys(self):
        result = _extract_components(["CCO", "c1ccccc1"])
        assert "scaffolds" in result
        assert "fragments" in result

    def test_empty_input_returns_empty_lists(self):
        result = _extract_components([])
        assert result["scaffolds"] == []
        assert result["fragments"] == []

    def test_invalid_smiles_does_not_raise(self):
        # Should not raise even if RDKit is unavailable or SMILES is invalid
        _extract_components(["not_a_smiles_##$$"])

    def test_fragment_count_bounded(self):
        smiles_list = ["CCO", "CCCO", "CCCCO", "c1ccccc1", "c1cccnc1"]
        result = _extract_components(smiles_list)
        assert len(result["fragments"]) <= 40
        assert len(result["scaffolds"]) <= 30


# ─────────────────────────────────────────────────────────────────────────────
# _score_design_priority
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreDesignPriority:
    def test_all_none_returns_zero(self):
        result = _score_design_priority({})
        assert result == 0.0

    def test_binding_score_alone(self):
        result = _score_design_priority({"binding_score": 0.8})
        assert result == pytest.approx(80.0, abs=0.5)

    def test_full_data_bounded_0_to_100(self):
        lead = {
            "binding_score": 0.7,
            "opentargets_score": 0.6,
            "oral_exposure_score": 75.0,
            "toxicity_risk": 30.0,
            "synthesis_feasibility_score": 80.0,
        }
        result = _score_design_priority(lead)
        assert 0.0 <= result <= 100.0
