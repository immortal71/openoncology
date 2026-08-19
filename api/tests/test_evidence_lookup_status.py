"""A failed evidence lookup must be attributable to the variant it failed for.

risk_analysis.md F3, remaining half. Migration 0013 recorded that the evidence
base was degraded when a result was produced. It could not say which gene's
lookup was the one that failed, so a four-variant report where one lookup broke
still read as four negatives.

The property under test throughout: "checked, nothing found" and "never
checked" must never render or serialise alike. That is the same asymmetry
pinned for sample QC (0011) and evidence provenance (0013).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from models.mutation import EvidenceLookupStatus  # noqa: E402
from services.oncologist_report import generate_oncologist_report  # noqa: E402


class TestStatusEnum:
    def test_three_distinct_states(self):
        values = {s.value for s in EvidenceLookupStatus}
        assert values == {"ok", "not_attempted", "unavailable"}

    def test_failure_states_are_not_equal_to_ok(self):
        assert EvidenceLookupStatus.unavailable != EvidenceLookupStatus.ok
        assert EvidenceLookupStatus.not_attempted != EvidenceLookupStatus.ok


class TestWorkerRecordsStatus:
    """_query_oncokb_with_status must distinguish the two ways of failing."""

    def test_missing_token_is_not_attempted(self, monkeypatch):
        import workers.ai_worker as w

        class _S:
            oncokb_api_token = ""

        monkeypatch.setitem(sys.modules, "config", type("m", (), {"settings": _S})())
        data, status = w._query_oncokb_with_status("EGFR", "p.L858R")
        assert data is None
        assert status is EvidenceLookupStatus.not_attempted

    def test_request_failure_is_unavailable(self, monkeypatch):
        import workers.ai_worker as w

        class _S:
            oncokb_api_token = "tok"

        monkeypatch.setitem(sys.modules, "config", type("m", (), {"settings": _S})())

        import httpx

        def _boom(*a, **k):
            raise httpx.ConnectError("network down")

        monkeypatch.setattr(httpx, "get", _boom)
        data, status = w._query_oncokb_with_status("EGFR", "p.L858R")
        assert data is None
        assert status is EvidenceLookupStatus.unavailable

    def test_legacy_wrapper_contract_is_unchanged(self, monkeypatch):
        """_query_oncokb still returns dict|None so existing callers are safe."""
        import workers.ai_worker as w

        class _S:
            oncokb_api_token = ""

        monkeypatch.setitem(sys.modules, "config", type("m", (), {"settings": _S})())
        assert w._query_oncokb("EGFR", "p.L858R") is None


class TestReportRendersTheDistinction:
    def _report(self, status):
        mutation = {
            "gene": "EGFR",
            "hgvs_notation": "p.L858R",
            "classification": "pathogenic",
            "oncokb_level": None,
            "is_targetable": False,
        }
        if status is not _SENTINEL:
            mutation["evidence_lookup_status"] = status
        return generate_oncologist_report(
            ranked_candidates=[],
            mutation_summary=[mutation],
            cancer_type="Lung adenocarcinoma",
        )

    def test_failed_lookup_is_flagged_in_plain_text(self):
        report = self._report("unavailable")
        text = report.plain_text or ""
        assert "lookup FAILED" in text
        assert "NOT established" in text

    def test_never_queried_is_flagged_distinctly(self):
        text = self._report("not_attempted").plain_text or ""
        assert "never queried" in text
        assert "lookup FAILED" not in text

    def test_successful_lookup_is_not_annotated(self):
        text = self._report("ok").plain_text or ""
        assert "lookup FAILED" not in text
        assert "never queried" not in text
        assert "not recorded" not in text

    def test_unrecorded_state_renders_as_unrecorded(self):
        text = self._report(None).plain_text or ""
        assert "not recorded" in text

    def test_failed_and_successful_do_not_render_alike(self):
        assert (self._report("unavailable").plain_text
                != self._report("ok").plain_text)

    def test_status_is_carried_onto_the_alteration_row(self):
        report = self._report("unavailable")
        assert report.genomic_alterations
        assert report.genomic_alterations[0]["evidence_lookup_status"] == "unavailable"


_SENTINEL = object()
