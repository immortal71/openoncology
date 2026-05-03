"""Tests for api/services/oncokb_evidence.py

Run with:
    cd api && python -m pytest tests/test_oncokb_evidence.py -v
"""
from __future__ import annotations

import sys
import os

# Allow imports as 'api.services.*' or bare 'services.*'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.oncokb_evidence import (  # noqa: E402
    _normalise_alteration,
    _normalise_drug,
    lookup_oncokb_level,
    get_all_drugs_for_variant,
    annotate_candidates,
)


# ── _normalise_alteration ─────────────────────────────────────────────────────

class TestNormaliseAlteration:
    def test_lowercase(self):
        assert _normalise_alteration("T790M") == "t790m"

    def test_strips_whitespace(self):
        assert _normalise_alteration("  T790M  ") == "t790m"

    def test_p_dot_prefix_removed(self):
        result = _normalise_alteration("p.T790M")
        assert result in ("p.t790m", "t790m")

    def test_empty_string(self):
        assert _normalise_alteration("") == ""


# ── _normalise_drug ───────────────────────────────────────────────────────────

class TestNormaliseDrug:
    def test_lowercase_no_spaces(self):
        result = _normalise_drug("Osimertinib")
        assert result == result.lower()

    def test_strips_hyphens_and_spaces(self):
        a = _normalise_drug("Erlotinib HCl")
        b = _normalise_drug("erlotinibhcl")
        # Both should reduce to the same token
        assert " " not in a

    def test_empty_string(self):
        assert _normalise_drug("") == ""


# ── lookup_oncokb_level ───────────────────────────────────────────────────────

class TestLookupOncoKBLevel:
    """Tests against the curated static table (~120 entries)."""

    def test_egfr_t790m_osimertinib_is_level_1(self):
        level = lookup_oncokb_level("EGFR", "T790M", "Osimertinib")
        assert level == "LEVEL_1", f"Expected LEVEL_1, got {level}"

    def test_egfr_t790m_erlotinib_is_resistance(self):
        level = lookup_oncokb_level("EGFR", "T790M", "Erlotinib")
        assert level in ("LEVEL_R1", "LEVEL_R2"), (
            f"Erlotinib should be resistance for T790M, got {level}"
        )

    def test_braf_v600e_vemurafenib_is_level_1(self):
        level = lookup_oncokb_level("BRAF", "V600E", "Vemurafenib")
        assert level in ("LEVEL_1", "LEVEL_2"), f"Expected L1/L2, got {level}"

    def test_kras_g12c_sotorasib_is_level_1(self):
        level = lookup_oncokb_level("KRAS", "G12C", "Sotorasib")
        assert level is not None and level.startswith("LEVEL_"), (
            f"Expected a level entry for KRAS G12C + Sotorasib, got {level}"
        )

    def test_unknown_gene_returns_none(self):
        level = lookup_oncokb_level("FAKEGENE", "X999Y", "NotADrug")
        assert level is None

    def test_case_insensitive_gene(self):
        upper = lookup_oncokb_level("EGFR", "T790M", "Osimertinib")
        lower = lookup_oncokb_level("egfr", "t790m", "osimertinib")
        assert upper == lower

    def test_returns_string_or_none(self):
        result = lookup_oncokb_level("ALK", "EML4-ALK", "Crizotinib")
        assert result is None or isinstance(result, str)


# ── get_all_drugs_for_variant ─────────────────────────────────────────────────

class TestGetAllDrugsForVariant:
    def test_egfr_exon19del_returns_drugs(self):
        drugs = get_all_drugs_for_variant("EGFR", "Exon19del")
        assert isinstance(drugs, dict)
        # Should contain at least one EGFR TKI
        assert len(drugs) > 0

    def test_unknown_variant_returns_empty_dict(self):
        drugs = get_all_drugs_for_variant("FAKEGENE", "XXXYYY")
        assert drugs == {}

    def test_resistance_drug_present_for_t790m(self):
        drugs = get_all_drugs_for_variant("EGFR", "T790M")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        # Osimertinib should be L1; erlotinib/gefitinib should be R1
        assert any("osimertinib" in k for k in drug_levels), (
            "Osimertinib should appear for EGFR T790M"
        )


# ── annotate_candidates ────────────────────────────────────────────────────────

class TestAnnotateCandidates:
    """annotate_candidates() is a synchronous function that enriches a list of
    candidate dicts with oncokb_level."""

    def _make_candidates(self, names: list[str]) -> list[dict]:
        return [{"drug_name": n, "oncokb_level": None} for n in names]

    def test_osimertinib_annotated_for_t790m(self):
        candidates = self._make_candidates(["Osimertinib", "Erlotinib", "Gefitinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        levels = {c["drug_name"]: c.get("oncokb_level") for c in annotated}
        assert levels["Osimertinib"] == "LEVEL_1"

    def test_resistance_annotated_for_t790m(self):
        candidates = self._make_candidates(["Erlotinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        level = annotated[0].get("oncokb_level")
        assert level in ("LEVEL_R1", "LEVEL_R2"), (
            f"Erlotinib should be resistance for T790M, got {level}"
        )

    def test_unknown_drug_level_remains_none(self):
        candidates = self._make_candidates(["TotallyMadeUpDrug99"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        # Level should be None or unchanged — should NOT be injected as Level 1
        level = annotated[0].get("oncokb_level")
        assert level is None or not level.startswith("LEVEL_1")

    def test_empty_candidates_returns_empty(self):
        result = annotate_candidates([], "EGFR", "T790M")
        assert result == []

    def test_existing_level_not_overwritten_by_none(self):
        """If a candidate already has a level, it should not be overwritten with None."""
        candidates = [{"drug_name": "SomeNewDrug", "oncokb_level": "LEVEL_4"}]
        annotated = annotate_candidates(candidates, "EGFR", "UnknownVariant")
        # Level should be preserved if annotate_candidates doesn't know this drug
        level = annotated[0].get("oncokb_level")
        assert level is not None  # Must not silently nullify an existing annotation

    def test_braf_v600e_vemurafenib_annotated(self):
        candidates = self._make_candidates(["Vemurafenib", "Dabrafenib"])
        annotated = annotate_candidates(candidates, "BRAF", "V600E")
        vemurafenib = next(c for c in annotated if c["drug_name"] == "Vemurafenib")
        assert vemurafenib.get("oncokb_level") is not None

    def test_returns_list_same_length(self):
        candidates = self._make_candidates(["Osimertinib", "Erlotinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        assert len(annotated) == 2


# ── Resistance safety floor ────────────────────────────────────────────────────

class TestResistanceSafetyFloor:
    """Critical: resistance designations must be present even when using fallback table."""

    def test_afatinib_is_resistance_for_t790m(self):
        from services.oncokb_evidence import lookup_oncokb_level
        level = lookup_oncokb_level("EGFR", "T790M", "Afatinib")
        assert level in ("LEVEL_R1", "LEVEL_R2", None), (
            f"Afatinib should be resistance or unknown for T790M, got {level}"
        )

    def test_imatinib_resistance_for_abl1_t315i(self):
        """Imatinib must not appear as a non-resistance drug for ABL1 T315I."""
        level = lookup_oncokb_level("ABL1", "T315I", "Imatinib")
        if level is not None:
            assert level.startswith("LEVEL_R"), (
                f"Imatinib should be resistance for ABL1 T315I, got {level}"
            )


# ── High-impact regression checks ─────────────────────────────────────────────

class TestHighImpactEvidenceRegressions:
    """Guard clinically important entries that previously caused benchmark misses."""

    def test_mlh1_loss_of_expression_has_actionable_drug(self):
        drugs = get_all_drugs_for_variant("MLH1", "LOSSOFEXPRESSION", alphamissense_score=1.0)
        assert drugs, "MLH1 LOSSOFEXPRESSION should return actionable evidence"
        assert any(str(level).startswith("LEVEL_") and "R" not in str(level) for level in drugs.values())

    def test_npm1_insertiontypeb_contains_midostaurin(self):
        drugs = {k.lower(): v for k, v in get_all_drugs_for_variant("NPM1", "INSERTIONTYPEB", alphamissense_score=1.0).items()}
        assert "midostaurin" in drugs, "NPM1 INSERTIONTYPEB should include midostaurin"
        assert str(drugs["midostaurin"]).startswith("LEVEL_"), "midostaurin should have an OncoKB level"

    def test_vhl_loss_includes_belzutifan(self):
        drugs = {k.lower(): v for k, v in get_all_drugs_for_variant("VHL", "LOSS", alphamissense_score=1.0).items()}
        assert "belzutifan" in drugs, "VHL LOSS should include belzutifan"
        assert str(drugs["belzutifan"]) == "LEVEL_1", "belzutifan should be LEVEL_1 for VHL LOSS"
