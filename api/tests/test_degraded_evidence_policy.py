"""Policy for answering from an evidence base of unknown currency.

risk_analysis.md F4 left one thing open: nothing *refused* to answer from the
undated static table, and nothing alerted on a sustained fallback. The state was
reportable, not prevented. Open action 4 asked whether a degraded evidence base
should block output at all.

The answer implemented here is that it depends on deployment, so it is a setting
rather than a hardcoded branch:

  * research use (default)  — flag loudly, keep answering
  * clinical use            — refuse, because a recommendation from evidence of
                              unknown currency is exactly the H4 hazard

Both halves are pinned below, plus the sustained-fallback alarm, because a
policy that is never exercised is the F10 pattern again.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

import services.oncokb_evidence as ev  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_provenance():
    ev._CONSECUTIVE_STATIC_FALLBACKS = 0
    yield
    ev._CONSECUTIVE_STATIC_FALLBACKS = 0


class TestPolicyDefaultIsResearchUse:
    def test_degraded_evidence_does_not_raise_by_default(self, monkeypatch):
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        monkeypatch.setattr(
            "config.settings.require_current_evidence", False, raising=False
        )
        provenance = ev.enforce_evidence_policy()
        assert provenance["is_current"] is False

    def test_current_evidence_never_raises(self, monkeypatch):
        ev._record_evidence_provenance(ev.PROVENANCE_DOWNLOAD)
        monkeypatch.setattr(
            "config.settings.require_current_evidence", True, raising=False
        )
        provenance = ev.enforce_evidence_policy()
        assert provenance["is_current"] is True


class TestPolicyRefusesWhenRequired:
    def test_static_fallback_raises_when_current_evidence_required(self, monkeypatch):
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        monkeypatch.setattr(
            "config.settings.require_current_evidence", True, raising=False
        )
        with pytest.raises(ev.DegradedEvidenceError) as excinfo:
            ev.enforce_evidence_policy()
        assert "static_fallback" in str(excinfo.value)
        assert excinfo.value.provenance["is_current"] is False

    def test_error_carries_the_provenance_for_the_caller_to_record(self, monkeypatch):
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        monkeypatch.setattr(
            "config.settings.require_current_evidence", True, raising=False
        )
        try:
            ev.enforce_evidence_policy()
        except ev.DegradedEvidenceError as exc:
            assert exc.provenance["path"] == ev.PROVENANCE_STATIC_FALLBACK
        else:
            pytest.fail("expected DegradedEvidenceError")


class TestSustainedFallbackAlarm:
    def test_single_fallback_does_not_escalate_to_error(self, caplog, monkeypatch):
        monkeypatch.setattr(
            "config.settings.degraded_evidence_alert_after", 3, raising=False
        )
        with caplog.at_level(logging.ERROR):
            ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_sustained_fallback_escalates_to_error(self, caplog, monkeypatch):
        monkeypatch.setattr(
            "config.settings.degraded_evidence_alert_after", 3, raising=False
        )
        with caplog.at_level(logging.ERROR):
            for _ in range(3):
                ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert errors, "a sustained degraded run must escalate"
        assert "unknown currency" in errors[-1].getMessage()

    def test_a_good_resolution_resets_the_streak(self, monkeypatch):
        monkeypatch.setattr(
            "config.settings.degraded_evidence_alert_after", 3, raising=False
        )
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        ev._record_evidence_provenance(ev.PROVENANCE_STATIC_FALLBACK)
        assert ev.get_consecutive_static_fallbacks() == 2
        ev._record_evidence_provenance(ev.PROVENANCE_DOWNLOAD)
        assert ev.get_consecutive_static_fallbacks() == 0

    def test_streak_counts_only_consecutive_degraded_resolutions(self, monkeypatch):
        monkeypatch.setattr(
            "config.settings.degraded_evidence_alert_after", 3, raising=False
        )
        for path in (
            ev.PROVENANCE_STATIC_FALLBACK,
            ev.PROVENANCE_DOWNLOAD,
            ev.PROVENANCE_STATIC_FALLBACK,
        ):
            ev._record_evidence_provenance(path)
        assert ev.get_consecutive_static_fallbacks() == 1


class TestWithheldIsDistinctFromEmpty:
    """An empty recommendation list has two very different causes."""

    def test_withheld_reason_is_stamped_on_the_provenance(self):
        from workers.ai_worker import _capture_evidence_provenance

        payload = _capture_evidence_provenance(withheld_reason="policy says no")
        assert payload is not None
        assert payload["recommendations_withheld"] is True
        assert payload["withheld_reason"] == "policy says no"

    def test_normal_run_is_not_marked_withheld(self):
        from workers.ai_worker import _capture_evidence_provenance

        payload = _capture_evidence_provenance()
        assert payload is not None
        assert payload["recommendations_withheld"] is False
        assert "withheld_reason" not in payload

    def test_reason_survives_a_provenance_capture_failure(self, monkeypatch):
        """Losing provenance must not lose the reason the result is empty."""
        import workers.ai_worker as w

        monkeypatch.setattr(
            ev, "get_evidence_provenance", lambda: (_ for _ in ()).throw(RuntimeError("x"))
        )
        payload = w._capture_evidence_provenance(withheld_reason="policy says no")
        assert payload is not None
        assert payload["recommendations_withheld"] is True
        assert payload["is_current"] is False

    def test_schema_defaults_to_not_withheld(self):
        from schemas.responses import EvidenceProvenanceOut

        assert EvidenceProvenanceOut().recommendations_withheld is False
        assert EvidenceProvenanceOut().withheld_reason is None
