"""Tests for api/services/opentargets.py — all HTTP calls are mocked.

Covers:
  - get_target_id: returns Ensembl ID on success
  - get_target_id: returns None when no hits
  - get_target_id: returns None on network error
  - get_drugs_for_target: returns drug list with expected fields
  - get_drugs_for_target: respects max_drugs limit
  - get_drugs_for_target: returns empty list when target not found
  - get_drugs_for_target: returns empty list on network error
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from api.services.opentargets import get_target_id, get_drugs_for_target


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_post_response(data: dict) -> MagicMock:
    """Create a mock httpx response that returns the given data."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"data": data})
    return resp


def _make_gql_post_mock(return_data: dict):
    """Context manager mock for httpx.AsyncClient with a .post method."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_post_response(return_data))
    return mock_client


# ── get_target_id ─────────────────────────────────────────────────────────────

class TestGetTargetId:
    async def test_returns_ensembl_id_on_hit(self):
        data = {
            "search": {
                "hits": [{"id": "ENSG00000146648", "object": {"approvedSymbol": "EGFR"}}]
            }
        }
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(data)
            result = await get_target_id("EGFR")

        assert result == "ENSG00000146648"

    async def test_returns_none_when_no_hits(self):
        data = {"search": {"hits": []}}
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(data)
            result = await get_target_id("FAKEGENE123")

        assert result is None

    async def test_returns_none_on_network_error(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            cls.return_value = mock_client

            result = await get_target_id("EGFR")

        assert result is None

    async def test_returns_first_hit_id(self):
        """When multiple hits, should return the first one."""
        data = {
            "search": {
                "hits": [
                    {"id": "ENSG00000001", "object": {}},
                    {"id": "ENSG00000002", "object": {}},
                ]
            }
        }
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(data)
            result = await get_target_id("SOME_GENE")

        assert result == "ENSG00000001"


# ── get_drugs_for_target ──────────────────────────────────────────────────────

def _make_drugs_response(num_drugs: int = 2) -> dict:
    # OpenTargets returns maxClinicalStage as string labels, not integers.
    # "APPROVAL" → approved drug, "PHASE2" → phase 2 trial.
    rows = []
    for i in range(1, num_drugs + 1):
        rows.append({
            "id": f"CHEMBL{i}",
            "maxClinicalStage": "APPROVAL" if i == 1 else "PHASE2",
            "drug": {
                "id": f"CHEMBL{i}",
                "name": f"Drug{i}",
                "description": "Test drug",
                "mechanismsOfAction": {
                    "rows": [
                        {
                            "mechanismOfAction": "Kinase inhibitor",
                            "actionType": "INHIBITOR",
                        }
                    ]
                },
            },
            "diseases": [
                {
                    "diseaseFromSource": "lung cancer",
                    "disease": {"id": "EFO_0001071", "name": "lung carcinoma"},
                }
            ],
        })
    return {
        "target": {
            "id": "ENSG00000146648",
            "approvedSymbol": "EGFR",
            "drugAndClinicalCandidates": {
                "count": num_drugs,
                "rows": rows,
            },
        }
    }


class TestGetDrugsForTarget:
    async def test_returns_list_of_drugs(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(_make_drugs_response(2))
            drugs = await get_drugs_for_target("ENSG00000146648")

        assert len(drugs) == 2

    async def test_drug_has_required_fields(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(_make_drugs_response(1))
            drugs = await get_drugs_for_target("ENSG00000146648")

        d = drugs[0]
        assert "chembl_id" in d
        assert "drug_name" in d
        assert "max_phase" in d
        assert "mechanism" in d

    async def test_first_drug_is_approved(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(_make_drugs_response(2))
            drugs = await get_drugs_for_target("ENSG00000146648")

        # Drug1 has maxClinicalStage=4 → is_approved
        approved = [d for d in drugs if d.get("is_approved")]
        assert len(approved) >= 1

    async def test_max_drugs_limit_respected(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(_make_drugs_response(10))
            drugs = await get_drugs_for_target("ENSG00000146648", max_drugs=3)

        assert len(drugs) <= 3

    async def test_returns_empty_list_when_target_not_found(self):
        data = {"target": None}
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(data)
            drugs = await get_drugs_for_target("ENSG00000000000")

        assert drugs == []

    async def test_returns_empty_list_on_network_error(self):
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("network down"))
            cls.return_value = mock_client

            drugs = await get_drugs_for_target("ENSG00000146648")

        assert drugs == []

    async def test_empty_drug_list_in_response(self):
        data = {
            "target": {
                "id": "ENSG00000146648",
                "approvedSymbol": "EGFR",
                "drugAndClinicalCandidates": {"count": 0, "rows": []},
            }
        }
        with patch("api.services.opentargets.httpx.AsyncClient") as cls:
            cls.return_value = _make_gql_post_mock(data)
            drugs = await get_drugs_for_target("ENSG00000146648")

        assert drugs == []
