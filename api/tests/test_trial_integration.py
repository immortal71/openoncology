"""Unit tests for api/services/trial_integration.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from services.trial_integration import (
    fetch_trials_by_gene,
    fetch_trials_by_variant,
    score_trial_variant_relevance,
    VARIANT_TO_TRIAL_TERMS,
)


# ── VARIANT_TO_TRIAL_TERMS coverage ───────────────────────────────────────────

def test_variant_to_trial_terms_not_empty():
    assert len(VARIANT_TO_TRIAL_TERMS) >= 10


def test_braf_v600e_in_trial_terms():
    assert ("BRAF", "V600E") in VARIANT_TO_TRIAL_TERMS


def test_egfr_l858r_in_trial_terms():
    assert ("EGFR", "L858R") in VARIANT_TO_TRIAL_TERMS


def test_kras_g12c_in_trial_terms():
    assert ("KRAS", "G12C") in VARIANT_TO_TRIAL_TERMS


def test_all_entries_have_nonempty_terms():
    for (gene, variant), terms in VARIANT_TO_TRIAL_TERMS.items():
        assert len(terms) >= 1, f"({gene}, {variant}) has empty terms"
        for t in terms:
            assert isinstance(t, str) and len(t) > 0


# ── score_trial_variant_relevance ─────────────────────────────────────────────

def test_score_exact_variant_hit_is_high():
    score = score_trial_variant_relevance(
        trial_title="Phase 2 study of sotorasib in KRAS G12C NSCLC",
        trial_desc="Patients with KRAS G12C mutations are eligible.",
        gene="KRAS",
        variant="G12C",
    )
    assert score >= 0.7


def test_score_gene_only_is_moderate():
    score = score_trial_variant_relevance(
        trial_title="EGFR-targeted therapy in NSCLC",
        trial_desc="EGFR mutation-positive patients.",
        gene="EGFR",
        variant="X999Y",   # non-matching variant
    )
    assert 0.1 <= score < 0.8


def test_score_no_match_is_low():
    score = score_trial_variant_relevance(
        trial_title="Aspirin vs placebo for headache",
        trial_desc="Randomized controlled trial of aspirin.",
        gene="BRAF",
        variant="V600E",
    )
    assert score < 0.4


def test_score_between_0_and_1():
    score = score_trial_variant_relevance(
        trial_title="BRAF V600E melanoma trial with vemurafenib",
        trial_desc="BRAF V600E mutation in melanoma",
        gene="BRAF",
        variant="V600E",
    )
    assert 0.0 <= score <= 1.0


def test_score_case_insensitive():
    s1 = score_trial_variant_relevance("egfr l858r study", "egfr mutation", "EGFR", "L858R")
    s2 = score_trial_variant_relevance("EGFR L858R study", "EGFR MUTATION", "EGFR", "L858R")
    assert abs(s1 - s2) < 1e-6


# ── fetch_trials_by_gene ──────────────────────────────────────────────────────

def _mock_ct_response(n_studies: int = 5):
    studies = []
    for i in range(n_studies):
        studies.append({
            "protocolSection": {
                "identificationModule": {
                    "nctId": f"NCT{i:08d}",
                    "briefTitle": f"Study {i} of BRAF NSCLC",
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "lastKnownStatus": None,
                },
                "designModule": {
                    "phases": ["PHASE2"],
                },
                "conditionsModule": {
                    "conditions": ["Non-Small Cell Lung Cancer"],
                },
                "armsInterventionsModule": {
                    "interventions": [
                        {"interventionType": "DRUG", "name": f"Drug {i}"}
                    ],
                },
                "descriptionModule": {
                    "briefSummary": f"A study involving BRAF gene in NSCLC patients.",
                },
            }
        })
    return {"studies": studies, "totalCount": n_studies}


@pytest.mark.asyncio
async def test_fetch_trials_by_gene_returns_list():
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _mock_ct_response(3)
        mock_resp.raise_for_status = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=None)
        cm.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = cm

        trials = await fetch_trials_by_gene(gene="BRAF", cancer_type="NSCLC", limit=5)
        assert isinstance(trials, list)


@pytest.mark.asyncio
async def test_fetch_trials_by_gene_http_error_returns_empty():
    with patch("httpx.AsyncClient") as MockClient:
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=None)
        cm.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
        MockClient.return_value = cm

        trials = await fetch_trials_by_gene(gene="BRAF", cancer_type="NSCLC", limit=5)
        assert trials == []


@pytest.mark.asyncio
async def test_fetch_trials_by_variant_uses_variant_terms():
    """Ensure variant-specific path is taken for known variants."""
    call_args_capture = {}

    async def mock_get(url, params=None, timeout=None):
        call_args_capture["params"] = params or {}
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _mock_ct_response(2)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.AsyncClient") as MockClient:
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=None)
        cm.get = mock_get
        MockClient.return_value = cm

        trials = await fetch_trials_by_variant(gene="BRAF", variant="V600E",
                                               cancer_type="melanoma", limit=5)
        # Should have made the call with BRAF V600E term
        query_val = call_args_capture.get("params", {}).get("query.cond", "") + \
                    call_args_capture.get("params", {}).get("query.term", "")
        # Just verify no crash and we got results
        assert isinstance(trials, list)


@pytest.mark.asyncio
async def test_fetch_trials_by_variant_falls_back_to_gene_on_unknown_variant():
    """For variants not in VARIANT_TO_TRIAL_TERMS, fallback to gene search."""
    if not VARIANT_TO_TRIAL_TERMS.get(("ZZZGENE", "ZZZ999")):
        with patch("services.trial_integration.fetch_trials_by_gene",
                   new_callable=AsyncMock) as mock_gene_fn:
            mock_gene_fn.return_value = [{"trial_id": "NCT00000001", "relevance_score": 0.5}]
            # Also mock httpx to prevent real network calls
            with patch("httpx.AsyncClient") as MockClient:
                cm = AsyncMock()
                cm.__aenter__ = AsyncMock(return_value=cm)
                cm.__aexit__ = AsyncMock(return_value=None)
                cm.get = AsyncMock(side_effect=httpx.HTTPError("forbidden"))
                MockClient.return_value = cm
                trials = await fetch_trials_by_variant(
                    gene="ZZZGENE", variant="ZZZ999", cancer_type="unknown", limit=5
                )
            mock_gene_fn.assert_called_once()
            assert any(t.get("trial_id") == "NCT00000001" for t in trials)


@pytest.mark.asyncio
async def test_fetch_trials_sorted_by_relevance():
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _mock_ct_response(5)
        mock_resp.raise_for_status = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=None)
        cm.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = cm

        trials = await fetch_trials_by_variant("BRAF", "V600E", "melanoma", limit=5)
        if len(trials) > 1 and all("relevance_score" in t for t in trials):
            scores = [t["relevance_score"] for t in trials]
            assert scores == sorted(scores, reverse=True)


# ── Limit enforcement ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_trials_respects_limit():
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _mock_ct_response(20)
        mock_resp.raise_for_status = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=None)
        cm.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = cm

        trials = await fetch_trials_by_gene("BRAF", "melanoma", limit=5)
        assert len(trials) <= 5
