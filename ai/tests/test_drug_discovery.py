"""Tests for custom discovery brief generation service."""

import pytest


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
