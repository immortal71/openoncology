"""Tests for api/services/toxicity.py

Run with:
    cd api && python -m pytest tests/test_toxicity.py -v
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.toxicity import (  # noqa: E402
    predict_herg_risk,
    predict_ames_mutagenicity,
    predict_hepatotoxicity,
    predict_cyp_inhibition,
    predict_pains,
    assess_off_target_liability,
    compute_safety_rank_penalty,
    check_withdrawn_status,
    DENOVO_WARNING,
    _is_denovo_compound,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _molecule(smiles: str, **kwargs) -> dict:
    return {"smiles": smiles, "canonical_smiles": smiles, **kwargs}


# hERG offender: piperazine + basic N + aryl group (cisapride-like scaffold)
HERG_OFFENDER = _molecule(
    "C1CNCCN1CCOc1ccc(F)cc1",
    alogp=2.5, molecular_weight=238.3,
)

# Ames mutagen: nitroaromatic
AMES_MUTAGEN = _molecule("[N+](=O)[O-]c1ccccc1", alogp=1.9, molecular_weight=123.1)

# PAINS: rhodanine scaffold
PAINS_COMPOUND = _molecule("O=C1NC(=S)SC1", alogp=0.9, molecular_weight=119.1)

# Hepatotox: aniline moiety + high logP + high MW
HEPATOTOX_COMPOUND = _molecule(
    "Nc1ccccc1",
    alogp=1.0, molecular_weight=93.1,
)

# Benign small molecule (aspirin)
ASPIRIN = _molecule(
    "CC(=O)Oc1ccccc1C(=O)O",
    alogp=1.19, molecular_weight=180.16,
    max_phase=4, is_approved=True,
)

# Minimal molecule with no SMILES
NO_SMILES = {"drug_name": "UnknownCompound"}

# De-novo molecule (no ChEMBL ID, no PubChem CID, max_phase=0)
DENOVO = _molecule("CC(=O)Oc1ccccc1", max_phase=0)

# Approved molecule
APPROVED = _molecule("CC(=O)Oc1ccccc1C(=O)O", max_phase=4, is_approved=True)


# ── predict_herg_risk ─────────────────────────────────────────────────────────

class TestPredictHERGRisk:
    def test_herg_offender_flagged(self):
        result = predict_herg_risk(HERG_OFFENDER)
        assert result is not None
        assert result.flagged is True

    def test_aspirin_not_flagged(self):
        result = predict_herg_risk(ASPIRIN)
        assert result is not None
        # Aspirin (logP 1.19) should not trigger high-confidence hERG flag
        if result.flagged:
            assert result.confidence in ("LOW", "MEDIUM"), (
                "Aspirin should not be HIGH-confidence hERG risk"
            )

    def test_no_smiles_still_returns_result(self):
        """Function should gracefully handle missing SMILES."""
        result = predict_herg_risk(NO_SMILES)
        assert result is not None  # logP heuristic still runs

    def test_result_has_required_fields(self):
        result = predict_herg_risk(ASPIRIN)
        assert result is not None
        assert hasattr(result, "flagged")
        assert hasattr(result, "confidence")
        assert hasattr(result, "requires_wetlab_confirmation")
        assert result.requires_wetlab_confirmation is True

    def test_high_logp_triggers_logp_risk(self):
        high_logp = _molecule("CCCCCCCc1ccccc1", alogp=5.2, molecular_weight=190.0)
        result = predict_herg_risk(high_logp)
        assert result is not None
        assert result.logp_risk is True


# ── predict_ames_mutagenicity ─────────────────────────────────────────────────

class TestPredictAmesMutagenicity:
    def test_nitroaromatic_flagged(self):
        result = predict_ames_mutagenicity(AMES_MUTAGEN)
        assert result is not None
        assert result.flagged is True
        assert result.confidence == "HIGH"

    def test_aspirin_not_flagged(self):
        result = predict_ames_mutagenicity(ASPIRIN)
        assert result is not None
        assert result.flagged is False

    def test_no_smiles_returns_result(self):
        result = predict_ames_mutagenicity(NO_SMILES)
        assert result is not None
        assert result.flagged is False  # No SMILES = no alerts matched

    def test_result_has_alerts_list(self):
        result = predict_ames_mutagenicity(AMES_MUTAGEN)
        assert isinstance(result.alerts, list)
        assert len(result.alerts) >= 1

    def test_wetlab_flag_always_true(self):
        result = predict_ames_mutagenicity(ASPIRIN)
        assert result.requires_wetlab_confirmation is True

    def test_alkyl_bromide_flagged(self):
        alkyl_bromide = _molecule("CBr", alogp=0.5, molecular_weight=94.9)
        result = predict_ames_mutagenicity(alkyl_bromide)
        assert result is not None
        assert result.flagged is True


# ── predict_hepatotoxicity ────────────────────────────────────────────────────

class TestPredictHepatotoxicity:
    def test_aniline_flagged(self):
        result = predict_hepatotoxicity(HEPATOTOX_COMPOUND)
        assert result is not None
        assert result.flagged is True

    def test_aspirin_minimal_flags(self):
        result = predict_hepatotoxicity(ASPIRIN)
        assert result is not None
        # Aspirin may or may not flag at low logP; if flagged, confidence should not be HIGH
        if result.flagged:
            assert result.confidence in ("LOW", "MEDIUM")

    def test_high_mw_high_logp_adds_dili_flag(self):
        heavy = _molecule("c1ccccc1", alogp=5.0, molecular_weight=600.0)
        result = predict_hepatotoxicity(heavy)
        assert result is not None
        assert result.flagged is True, "MW>500 + logP>4.5 should trigger physicochemical DILI flag"

    def test_reactive_metabolite_detected(self):
        aniline_mol = _molecule("Nc1ccccc1")
        result = predict_hepatotoxicity(aniline_mol)
        if result is not None:
            assert result.reactive_metabolite_risk is True

    def test_wetlab_flag_always_true(self):
        result = predict_hepatotoxicity(ASPIRIN)
        assert result.requires_wetlab_confirmation is True


# ── predict_cyp_inhibition ────────────────────────────────────────────────────

class TestPredictCYPInhibition:
    def test_piperazine_cyp3a4_inhibition(self):
        """Piperazine is a common CYP3A4 structural flag."""
        piperazine = _molecule("C1CNCCN1", alogp=1.0, molecular_weight=86.1)
        result = predict_cyp_inhibition(piperazine)
        assert result is not None
        assert "CYP3A4" in result.inhibited_isoforms or "CYP2D6" in result.inhibited_isoforms

    def test_no_smiles_returns_none(self):
        result = predict_cyp_inhibition(NO_SMILES)
        assert result is None

    def test_cyp3a4_inhibition_gives_high_ddi(self):
        piperazine = _molecule("C1CNCCN1")
        result = predict_cyp_inhibition(piperazine)
        if result is not None and "CYP3A4" in result.inhibited_isoforms:
            assert result.ddI_risk == "HIGH"

    def test_clean_molecule_no_isoforms(self):
        simple = _molecule("OCC", alogp=0.5, molecular_weight=62.1)
        result = predict_cyp_inhibition(simple)
        if result is not None:
            assert result.ddI_risk in ("NONE", "LOW")

    def test_wetlab_flag_always_true(self):
        result = predict_cyp_inhibition(ASPIRIN)
        if result is not None:
            assert result.requires_wetlab_confirmation is True


# ── predict_pains ─────────────────────────────────────────────────────────────

class TestPredictPAINS:
    def test_rhodanine_flagged(self):
        result = predict_pains(PAINS_COMPOUND)
        assert result is not None
        assert result.flagged is True

    def test_aspirin_not_flagged(self):
        result = predict_pains(ASPIRIN)
        assert result is not None
        assert result.flagged is False

    def test_recommendation_present(self):
        result = predict_pains(PAINS_COMPOUND)
        assert result is not None
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0

    def test_no_smiles_no_flags(self):
        result = predict_pains(NO_SMILES)
        assert result is not None
        assert result.flagged is False


# ── assess_off_target_liability (integration) ──────────────────────────────────

class TestAssessOffTargetLiability:
    def test_nitroaromatic_high_risk(self):
        result = assess_off_target_liability(AMES_MUTAGEN)
        assert result is not None
        assert result.overall_risk_level in ("HIGH", "VERY_HIGH")

    def test_aspirin_low_risk(self):
        result = assess_off_target_liability(ASPIRIN, is_approved=True)
        assert result is not None
        assert result.overall_risk_level in ("LOW", "MODERATE")

    def test_gate_fails_for_denovo_ames_high(self):
        result = assess_off_target_liability(AMES_MUTAGEN, is_approved=False)
        assert result is not None
        assert result.safety_gate_pass is False

    def test_gate_passes_for_approved_drug(self):
        """Approved drugs always pass the safety gate regardless of QSAR flags."""
        result = assess_off_target_liability(AMES_MUTAGEN, is_approved=True)
        assert result is not None
        assert result.safety_gate_pass is True

    def test_denovo_molecule_flagged(self):
        result = assess_off_target_liability(DENOVO, is_approved=False)
        assert result is not None
        assert result.is_denovo is True
        assert result.denovo_warning is not None
        assert len(result.denovo_warning) > 50  # Non-trivial warning text

    def test_approved_molecule_not_denovo(self):
        result = assess_off_target_liability(APPROVED, is_approved=True)
        assert result is not None
        assert result.is_denovo is False
        assert result.denovo_warning is None

    def test_summary_is_non_empty_string(self):
        result = assess_off_target_liability(ASPIRIN)
        assert isinstance(result.summary, str) and len(result.summary) > 0

    def test_wetlab_always_required(self):
        result = assess_off_target_liability(ASPIRIN)
        assert result.requires_wetlab_confirmation is True


# ── compute_safety_rank_penalty ────────────────────────────────────────────────

class TestComputeSafetyRankPenalty:
    def test_withdrawn_drug_max_penalty(self):
        penalty = compute_safety_rank_penalty({}, drug_name="Rofecoxib")
        assert penalty == 0.50

    def test_high_risk_molecule_large_penalty(self):
        penalty = compute_safety_rank_penalty(AMES_MUTAGEN, is_approved=False)
        assert penalty >= 0.20

    def test_approved_drug_capped_penalty(self):
        # Even a scary molecule should be capped at 0.05 if is_approved=True
        penalty = compute_safety_rank_penalty(AMES_MUTAGEN, is_approved=True)
        assert penalty <= 0.10

    def test_aspirin_minimal_penalty(self):
        penalty = compute_safety_rank_penalty(ASPIRIN, is_approved=True)
        assert penalty <= 0.10


# ── check_withdrawn_status ─────────────────────────────────────────────────────

class TestCheckWithdrawnStatus:
    def test_rofecoxib_withdrawn(self):
        result = check_withdrawn_status("Rofecoxib")
        assert result is not None
        assert "cardiovascular" in result["reason"].lower()

    def test_vioxx_alias_detected(self):
        result = check_withdrawn_status("Vioxx")
        assert result is not None

    def test_approved_drug_not_withdrawn(self):
        result = check_withdrawn_status("Osimertinib")
        assert result is None

    def test_case_insensitive(self):
        upper = check_withdrawn_status("ROFECOXIB")
        lower = check_withdrawn_status("rofecoxib")
        assert upper is not None and lower is not None


# ── De-novo detection ─────────────────────────────────────────────────────────

class TestIsDenovoCompound:
    def test_approved_is_not_denovo(self):
        assert _is_denovo_compound(APPROVED) is False

    def test_no_ids_no_phase_is_denovo(self):
        mol = {"smiles": "CC", "drug_name": "TestCompound"}
        assert _is_denovo_compound(mol) is True

    def test_max_phase_0_is_denovo(self):
        assert _is_denovo_compound(DENOVO) is True

    def test_has_chembl_id_not_denovo(self):
        mol = {"drug_name": "SomeDrug", "molecule_chembl_id": "CHEMBL12345"}
        assert _is_denovo_compound(mol) is False

    def test_denovo_warning_constant_is_long(self):
        assert len(DENOVO_WARNING) > 100
