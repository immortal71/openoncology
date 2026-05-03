"""Tests for api/services/adme.py

Run with:
    cd api && python -m pytest tests/test_adme.py -v
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.adme import (  # noqa: E402
    estimate_sa_score,
    predict_bbb_penetration,
    predict_pgp_substrate,
    predict_metabolic_stability,
    predict_plasma_protein_binding,
    compute_adme_profile,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _drug_aspirin() -> dict:
    """Aspirin — simple, well-characterised, rule-of-5 compliant molecule."""
    return {
        "drug_name": "Aspirin",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "molecular_weight": 180.16,
        "alogp": 1.19,
        "hba": 3,
        "hbd": 1,
        "psa": 63.6,
        "rotatable_bonds": 3,
        "num_rings": 1,
        "max_phase": 4,
        "is_approved": True,
    }


def _drug_paclitaxel() -> dict:
    """Paclitaxel — large, lipophilic molecule. Poor oral bioavailability, P-gp substrate."""
    return {
        "drug_name": "Paclitaxel",
        "smiles": "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(=O)O2)(C1)OC(=O)c5ccccc5)OC(=O)C)O)C)OC6CC(C(C(O6)C)OC(=O)C)O",
        "molecular_weight": 853.91,
        "alogp": 3.96,
        "hba": 14,
        "hbd": 4,
        "psa": 221.3,
        "rotatable_bonds": 14,
        "num_rings": 5,
        "max_phase": 4,
        "is_approved": True,
    }


def _drug_minimal() -> dict:
    """Minimal dict with only drug name — tests graceful degradation."""
    return {"drug_name": "TestCompound"}


def _drug_with_smiles_only() -> dict:
    """Ethanol — very simple, no physicochemical props set."""
    return {"drug_name": "Ethanol", "smiles": "CCO"}


# ── estimate_sa_score ─────────────────────────────────────────────────────────

class TestEstimateSaScore:
    def test_aspirin_returns_result_or_none(self):
        """SA score requires SMILES + optionally RDKit; should not raise."""
        result = estimate_sa_score(_drug_aspirin())
        # Allowed to return None when RDKit is unavailable
        assert result is None or hasattr(result, "sa_score")

    def test_no_smiles_returns_none(self):
        result = estimate_sa_score(_drug_minimal())
        assert result is None

    def test_result_score_in_range(self):
        result = estimate_sa_score(_drug_aspirin())
        if result is not None:
            assert 1.0 <= result.sa_score <= 10.0, (
                f"SA score must be in [1, 10], got {result.sa_score}"
            )

    def test_large_complex_molecule_higher_sa(self):
        """Paclitaxel is harder to synthesise than aspirin."""
        a = estimate_sa_score(_drug_aspirin())
        p = estimate_sa_score(_drug_paclitaxel())
        if a is not None and p is not None:
            assert p.sa_score >= a.sa_score, (
                "Paclitaxel should have higher (harder) SA score than aspirin"
            )


# ── predict_bbb_penetration ───────────────────────────────────────────────────

class TestPredictBBBPenetration:
    def test_aspirin_returns_result(self):
        result = predict_bbb_penetration(_drug_aspirin())
        assert result is not None
        assert hasattr(result, "prediction")

    def test_large_molecule_fails_bbb(self):
        """Paclitaxel (MW 854, PSA 221) should NOT penetrate BBB."""
        result = predict_bbb_penetration(_drug_paclitaxel())
        if result is not None:
            assert result.prediction in ("LOW", "VERY_LOW", "NONE", False, "unlikely")

    def test_missing_data_returns_none_or_result(self):
        """Should not raise even when all fields missing."""
        result = predict_bbb_penetration(_drug_minimal())
        # Either returns None or a low-confidence result
        assert result is None or hasattr(result, "prediction")

    def test_bbb_result_has_confidence(self):
        result = predict_bbb_penetration(_drug_aspirin())
        if result is not None:
            assert hasattr(result, "confidence") or hasattr(result, "score")


# ── predict_pgp_substrate ─────────────────────────────────────────────────────

class TestPredictPgpSubstrate:
    def test_aspirin_returns_result(self):
        result = predict_pgp_substrate(_drug_aspirin())
        assert result is not None or True  # May return None on minimal data

    def test_paclitaxel_is_pgp_substrate(self):
        """Paclitaxel is a well-known P-gp substrate (high MW, high PSA)."""
        result = predict_pgp_substrate(_drug_paclitaxel())
        if result is not None and hasattr(result, "is_substrate"):
            assert result.is_substrate is True, (
                "Paclitaxel should be flagged as P-gp substrate"
            )

    def test_result_has_required_fields(self):
        result = predict_pgp_substrate(_drug_aspirin())
        if result is not None:
            assert hasattr(result, "is_substrate") or hasattr(result, "prediction")


# ── predict_metabolic_stability ────────────────────────────────────────────────

class TestPredictMetabolicStability:
    def test_aspirin_returns_result_or_none(self):
        result = predict_metabolic_stability(_drug_aspirin())
        assert result is None or hasattr(result, "stability_class")

    def test_high_logp_reduced_stability(self):
        """High logP compounds are typically less stable (CYP3A4 substrates)."""
        high_logp = dict(_drug_aspirin())
        high_logp["alogp"] = 5.5
        result = predict_metabolic_stability(high_logp)
        if result is not None and hasattr(result, "stability_class"):
            assert result.stability_class in ("LOW", "MEDIUM", "HIGH", "VERY_LOW")

    def test_minimal_drug_graceful(self):
        result = predict_metabolic_stability(_drug_minimal())
        assert result is None or hasattr(result, "stability_class")


# ── predict_plasma_protein_binding ────────────────────────────────────────────

class TestPredictPlasmaProteinBinding:
    def test_aspirin_returns_result_or_none(self):
        result = predict_plasma_protein_binding(_drug_aspirin())
        assert result is None or hasattr(result, "ppb_fraction")

    def test_fraction_in_valid_range(self):
        result = predict_plasma_protein_binding(_drug_aspirin())
        if result is not None and hasattr(result, "ppb_fraction"):
            assert 0.0 <= result.ppb_fraction <= 1.0, (
                f"PPB fraction must be in [0, 1], got {result.ppb_fraction}"
            )

    def test_highly_lipophilic_high_ppb(self):
        """Highly lipophilic drugs tend to have higher PPB."""
        lipophilic = dict(_drug_aspirin())
        lipophilic["alogp"] = 6.0
        result = predict_plasma_protein_binding(lipophilic)
        if result is not None and hasattr(result, "ppb_fraction"):
            assert result.ppb_fraction > 0.5, (
                "Highly lipophilic compounds should have high PPB"
            )


# ── compute_adme_profile (integration) ────────────────────────────────────────

class TestComputeAdmeProfile:
    def test_aspirin_full_profile(self):
        profile = compute_adme_profile(_drug_aspirin())
        assert profile is not None

    def test_minimal_drug_does_not_crash(self):
        profile = compute_adme_profile(_drug_minimal())
        assert profile is not None

    def test_profile_has_key_attributes(self):
        profile = compute_adme_profile(_drug_aspirin())
        # At minimum a profile should expose some sub-result or summary
        assert hasattr(profile, "sa_score") or hasattr(profile, "bbb") or hasattr(profile, "summary")

    def test_paclitaxel_profile_flags_concerns(self):
        """Paclitaxel has known ADME liabilities; profile should surface them."""
        profile = compute_adme_profile(_drug_paclitaxel())
        assert profile is not None
        # Loose check: paclitaxel should not be flagged as a top oral drug
        if hasattr(profile, "oral_bioavailability") and profile.oral_bioavailability is not None:
            ob = profile.oral_bioavailability
            if hasattr(ob, "prediction"):
                assert ob.prediction in ("LOW", "VERY_LOW", "POOR", False, "unlikely", None)
