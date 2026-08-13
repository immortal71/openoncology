"""A recommendation must be able to say which evidence produced it.

risk_analysis.md F4: the actionability table resolves through a fresh cache, a
live download, or the undated hardcoded table, and which one answered was
recorded only as a log line. Nothing stored it, nothing returned it, so a
recommendation built from the static fallback was indistinguishable from one
built against a current OncoKB dump — and on 2026-08-13 every public dump URL
returned 401, so static_fallback was the *normal* path while recommendations
were produced as usual.

The property under test is one-directional: it is fine to under-claim currency,
never to over-claim it. Every unknown must land on is_current=False.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from services import oncokb_evidence as ev  # noqa: E402
from schemas.responses import EvidenceProvenanceOut, ResultsResponse  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_provenance():
    """The module keeps provenance in global state; put it back afterwards."""
    saved = dict(ev._EVIDENCE_PROVENANCE)
    yield
    ev._EVIDENCE_PROVENANCE.clear()
    ev._EVIDENCE_PROVENANCE.update(saved)


class TestProvenanceIsRetained:
    def test_a_download_is_recorded_as_current(self):
        ev._record_evidence_provenance(ev.PROVENANCE_DOWNLOAD)
        p = ev.get_evidence_provenance()
        assert p["path"] == "download"
        assert p["is_current"] is True
        assert p["caveat"] == ""
        assert p["snapshot_date"] is not None
        assert p["age_days"] == 0.0

    def test_a_fresh_cache_carries_the_file_age(self, tmp_path):
        cache = tmp_path / "cache.txt"
        cache.write_text("x", encoding="utf-8")
        ev._record_evidence_provenance(ev.PROVENANCE_FRESH_CACHE, cache)
        p = ev.get_evidence_provenance()
        assert p["path"] == "fresh_cache"
        assert p["is_current"] is True
        assert p["snapshot_date"] is not None
        assert 0 <= float(p["age_days"]) < 1

    def test_an_unreadable_cache_still_records_the_path(self, tmp_path):
        """A stat() failure must not lose the fact that the cache answered."""
        ev._record_evidence_provenance(ev.PROVENANCE_FRESH_CACHE, tmp_path / "missing.txt")
        p = ev.get_evidence_provenance()
        assert p["path"] == "fresh_cache"
        assert p["snapshot_date"] is None
        assert p["age_days"] is None


class TestTheDegradedPathIsNeverPresentedAsCurrent:
    def test_static_fallback_is_not_current_and_carries_a_caveat(self):
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        p = ev.get_evidence_provenance()
        assert p["path"] == "static_fallback"
        assert p["is_current"] is False
        assert "no version" in p["caveat"]
        assert p["snapshot_date"] is None, "the static table has no date to report"

    def test_an_unrecognised_path_is_not_current(self):
        """Failing towards 'we do not know' is the safe direction."""
        ev._EVIDENCE_PROVENANCE["path"] = "something_new"
        assert ev.get_evidence_provenance()["is_current"] is False

    def test_a_wiped_state_is_not_current(self):
        ev._EVIDENCE_PROVENANCE["path"] = None
        p = ev.get_evidence_provenance()
        assert p["path"] == "static_fallback"
        assert p["is_current"] is False

    def test_only_static_fallback_is_flagged(self):
        current = {ev.PROVENANCE_DOWNLOAD, ev.PROVENANCE_FRESH_CACHE, ev.PROVENANCE_LIVE_API}
        for path in current:
            ev._EVIDENCE_PROVENANCE["path"] = path
            assert ev.get_evidence_provenance()["is_current"] is True, path


class TestLiveApiProvenance:
    def test_it_keeps_the_table_path_alongside(self):
        """The static table is still merged in as a resistance floor, so say so."""
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        p = ev._live_api_provenance()
        assert p["path"] == "live_api"
        assert p["is_current"] is True
        assert p["table_path"] == "static_fallback"


class TestProvenanceReachesTheResponse:
    def test_the_metadata_function_returns_it(self):
        meta = ev.get_all_drugs_for_variant_live_with_metadata("EGFR", "L858R")
        assert "evidence_provenance" in meta
        assert "is_current" in meta["evidence_provenance"]

    def test_the_response_defaults_to_not_recorded(self):
        """A result predating capture must not read as having used current evidence."""
        response = ResultsResponse(submission_id="s1", status="complete")
        assert response.evidence_provenance.path == "not_recorded"
        assert response.evidence_provenance.is_current is False

    def test_the_response_accepts_a_real_provenance_block(self):
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        out = EvidenceProvenanceOut(**ev.get_evidence_provenance())
        assert out.is_current is False
        assert out.caveat

    def test_every_key_the_schema_declares_is_produced(self):
        """The adapter and the schema must not drift apart silently."""
        produced = set(ev.get_evidence_provenance())
        declared = set(EvidenceProvenanceOut.model_fields)
        assert produced <= declared, f"unmodelled keys: {produced - declared}"
