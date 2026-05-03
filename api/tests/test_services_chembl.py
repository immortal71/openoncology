"""Tests for api/services/chembl.py — all HTTP calls are mocked via respx.

Covers:
  - get_molecule: happy path with full properties
  - get_molecule: 404 returns None
  - get_molecule: network error returns None
  - get_molecule: ro5_pass flag set correctly
  - get_molecule: molecular_formula comes from props.full_mf (not inchi_key)
  - search_molecule_by_name: returns list of hits
  - search_molecule_by_name: empty result returns empty list
  - search_molecule_by_name: network error returns empty list
  - get_mechanisms_for_target: returns mechanism list
  - get_mechanisms_for_target: network error returns empty list
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from api.services.chembl import (
    get_molecule,
    search_molecule_by_name,
    get_mechanisms_for_target,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_molecule_response(
    chembl_id="CHEMBL25",
    pref_name="Aspirin",
    smiles="CC(=O)Oc1ccccc1C(=O)O",
    mf="C9H8O4",
    mwt="180.16",
    max_phase=4,
    ro5_violations=0,
):
    return {
        "molecule_chembl_id": chembl_id,
        "pref_name": pref_name,
        "max_phase": max_phase,
        "first_approval": 1950,
        "molecule_structures": {
            "canonical_smiles": smiles,
            "standard_inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        },
        "molecule_properties": {
            "full_mf": mf,
            "full_mwt": mwt,
            "alogp": "1.31",
            "hba": "4",
            "hbd": "1",
            "psa": "63.6",
            "rtb": "3",
            "num_ro5_violations": ro5_violations,
        },
    }


# ── get_molecule ──────────────────────────────────────────────────────────────

class TestGetMolecule:
    async def test_happy_path_returns_dict(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=_make_molecule_response())

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result is not None
        assert result["chembl_id"] == "CHEMBL25"
        assert result["preferred_name"] == "Aspirin"
        assert result["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"

    async def test_molecular_formula_from_full_mf_not_inchi_key(self):
        """Bug fix: molecular_formula must be full_mf, not standard_inchi_key."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_molecule_response(mf="C9H8O4")
        )

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        # Should be formula string like "C9H8O4", NOT an InChI key
        assert result["molecular_formula"] == "C9H8O4"
        assert not result["molecular_formula"].startswith("BSYNR")  # not InChI key

    async def test_ro5_pass_when_no_violations(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_molecule_response(ro5_violations=0)
        )

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result["ro5_pass"] is True

    async def test_ro5_fail_when_violations(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_molecule_response(ro5_violations=2)
        )

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result["ro5_pass"] is False

    async def test_is_approved_when_max_phase_4(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_molecule_response(max_phase=4)
        )

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result["is_approved"] is True

    async def test_not_approved_when_max_phase_less_than_4(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_molecule_response(max_phase=2)
        )

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result["is_approved"] is False

    async def test_404_returns_none(self):
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        http_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=error_response)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=http_error)

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL99999")

        assert result is None

    async def test_network_error_returns_none(self):
        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Network unreachable"))
            mock_client_cls.return_value = mock_client

            result = await get_molecule("CHEMBL25")

        assert result is None


# ── search_molecule_by_name ───────────────────────────────────────────────────

class TestSearchMoleculeByName:
    async def test_returns_list_of_hits(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "molecules": [
                {"molecule_chembl_id": "CHEMBL11", "pref_name": "Erlotinib", "max_phase": 4},
                {"molecule_chembl_id": "CHEMBL12", "pref_name": "Gefitinib", "max_phase": 4},
            ]
        })

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            results = await search_molecule_by_name("erlotinib")

        assert len(results) == 2
        assert results[0]["chembl_id"] == "CHEMBL11"
        assert results[0]["preferred_name"] == "Erlotinib"

    async def test_empty_result_returns_empty_list(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"molecules": []})

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            results = await search_molecule_by_name("xyzzy_not_real")

        assert results == []

    async def test_network_error_returns_empty_list(self):
        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_client_cls.return_value = mock_client

            results = await search_molecule_by_name("erlotinib")

        assert results == []


# ── get_mechanisms_for_target ─────────────────────────────────────────────────

class TestGetMechanismsForTarget:
    async def test_returns_mechanism_list(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "mechanisms": [
                {
                    "molecule_chembl_id": "CHEMBL553",
                    "mechanism_of_action": "Epidermal growth factor receptor inhibitor",
                    "action_type": "INHIBITOR",
                    "direct_interaction": True,
                }
            ]
        })

        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            results = await get_mechanisms_for_target("CHEMBL203")

        assert len(results) == 1
        assert results[0]["chembl_id"] == "CHEMBL553"
        assert results[0]["action_type"] == "INHIBITOR"
        assert results[0]["direct_interaction"] is True

    async def test_network_error_returns_empty_list(self):
        with patch("api.services.chembl.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client_cls.return_value = mock_client

            results = await get_mechanisms_for_target("CHEMBL203")

        assert results == []
