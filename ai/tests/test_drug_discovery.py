"""Tests for custom discovery brief generation service.

Includes tests for functions in drug_discovery.py.
These take plain Python values and return numbers.
"""

import pytest
from api.services.drug_discovery import (_clamp, _to_float, _phase_rank, _score_oral_exposure)


# _clamp() - keeps a value between a lower and upper limit.
def test_clamp_stays_at_max_when_value_is_too_high():
    """
    If a higher value than 1.0 is given, it defaults to 1.0.
    """
    assert _clamp(1.5) == 1.0

def test_clamp_returns_same_value_when_already_in_range():
    """
    If a value is already between 0.0 and 1.0, it stays the same.
    """
    assert _clamp(0.5) == 0.5

def test_clamp_stays_at_min_when_value_is_too_low():
    """
    If a value lower than 0.0 is given, it defaults to 0.0.
    """
    assert _clamp(-0.5) == 0.0


# _to_float() - converts inputs to a float.
def test_to_float_converts_a_number_written_as_a_string():
    """
    If a number is written as a string like "3.14", it should return 3.14.
    """
    assert _to_float("3.14") == 3.14

def test_to_float_returns_none_for_text_that_is_not_a_number():
    """
    If the input cannot be converted, like "abc", it should return None.
    """
    assert _to_float("abc") is None


# _to_float() - handles None, empty string, and numeric inputs.
def test_to_float_returns_none_for_none_input():
    """
    If None is given, there is nothing to convert so it should return None.
    """
    assert _to_float(None) is None

def test_to_float_returns_none_for_empty_string():
    """
    If an empty string is given, there is nothing to convert so it should return None.
    """
    assert _to_float("") is None


# _phase_rank() - maps phase label strings to integer ranks.
def test_phase_rank_converts_phase3_label_to_the_number_3():
    """
    If the string "PHASE3" is given, it should return the integer 3.
    """
    assert _phase_rank("PHASE3") == 3

def test_phase_rank_passes_an_integer_through_unchanged():
    """
    If an integer like 2 is given, it should pass through unchanged.
    """
    assert _phase_rank(2) == 2


# _score_oral_exposure() - takes a molecule dict and returns a score.
def test_score_oral_exposure_returns_none_when_no_molecule_data_is_given():
    """
    If the dict is empty, there is nothing to score so it returns None.
    """
    assert _score_oral_exposure({}) is None


@pytest.mark.asyncio
async def test_build_custom_discovery_brief_with_leads(monkeypatch):
    from api.services.drug_discovery import build_custom_discovery_brief

    async def _mock_get_target_id(_gene):
        return "ENSG000001"

    async def _mock_get_drugs_for_target(_ensg, max_drugs=40):
        return [
            {
                "chembl_id": "CHEMBL1",
                "drug_name": "LeadA",
                "mechanism": "Kinase inhibitor",
                "action_type": "INHIBITOR",
                "max_phase": 2,
                "is_approved": False,
                "opentargets_score": 0.82,
            },
            {
                "chembl_id": "CHEMBL2",
                "drug_name": "LeadB",
                "mechanism": "Allosteric modulator",
                "action_type": "MODULATOR",
                "max_phase": 3,
                "is_approved": False,
                "opentargets_score": 0.73,
            },
        ]

    async def _mock_get_molecule(chembl_id):
        if chembl_id == "CHEMBL1":
            return {
                "smiles": "CCOc1ccc(NC(=O)N)cc1",
                "max_phase": 2,
                "is_approved": False,
                "ro5_pass": True,
            }
        return {
            "smiles": "CCN(CC)CCOC1=CC=CC=C1",
            "max_phase": 3,
            "is_approved": False,
            "ro5_pass": True,
        }

    monkeypatch.setattr("api.services.drug_discovery.get_target_id", _mock_get_target_id)
    monkeypatch.setattr("api.services.drug_discovery.get_drugs_for_target", _mock_get_drugs_for_target)
    monkeypatch.setattr("api.services.drug_discovery.get_molecule", _mock_get_molecule)

    brief = await build_custom_discovery_brief(
        target_gene="EGFR",
        cancer_type="lung",
        mutation_hgvs=["p.L858R"],
        repurposing_candidates=[],
    )

    assert brief["mode"] == "custom_discovery"
    assert brief["target_gene"] == "EGFR"
    assert brief["ensembl_target_id"] == "ENSG000001"
    assert len(brief["lead_candidates"]) >= 2
    assert "component_library" in brief
    assert "fragments" in brief["component_library"]


@pytest.mark.asyncio
async def test_build_custom_discovery_brief_without_target_raises():
    from api.services.drug_discovery import build_custom_discovery_brief

    with pytest.raises(ValueError):
        await build_custom_discovery_brief(
            target_gene="",
            cancer_type="lung",
            mutation_hgvs=[],
        )
