"""A recommendation must name the rules that produced it.

REGULATORY_FRAMEWORK.md section 2.3 requires a locked algorithm version with a
change-control procedure before a De Novo or CE IVD-R submission. The question a
regulator asks is not what the system recommends, it is what exactly produced a
given recommendation and whether that has changed since.

`results.evidence_provenance` (0013) already says which evidence answered and
`mutations.evidence_lookup_status` (0014) says whether a lookup succeeded.
Neither says which scoring behaviour ran, so two recommendations built from
identical evidence could differ because a weight moved and nothing recorded it.

The change-control half is the last class here. `ALGORITHM_VERSION` is moved by
hand; the fingerprint moves on its own. When they disagree, that test fails and
someone has to decide which of the two is wrong. That is the whole mechanism:
code cannot lock an algorithm, it can only make a change impossible to make
quietly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _API_DIR.parent
for _p in (str(_API_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.algorithm_version import (  # noqa: E402
    ALGORITHM_VERSION,
    algorithm_fingerprint,
    describe_for_report,
    get_algorithm_version,
)


class TestFingerprintIsStable:
    def test_repeated_calls_agree(self):
        assert algorithm_fingerprint() == algorithm_fingerprint()

    def test_it_is_a_short_hex_digest(self):
        fp = algorithm_fingerprint()
        assert len(fp) == 16
        int(fp, 16)

    def test_the_block_carries_version_and_fingerprint(self):
        block = get_algorithm_version()
        assert block["version"] == ALGORITHM_VERSION
        assert block["fingerprint"] == algorithm_fingerprint()

    def test_report_line_is_human_readable(self):
        line = describe_for_report()
        assert ALGORITHM_VERSION in line
        assert algorithm_fingerprint() in line


class TestFingerprintTracksWhatChangesOutput:
    """It has to move when behaviour moves, or it is decoration."""

    def test_pool_policy_changes_the_fingerprint(self, monkeypatch):
        before = algorithm_fingerprint()
        monkeypatch.setattr(
            "config.settings.candidate_pool_policy", "tier2", raising=False
        )
        assert algorithm_fingerprint() != before

    def test_civic_supplement_changes_the_fingerprint(self, monkeypatch):
        before = algorithm_fingerprint()
        monkeypatch.setattr(
            "config.settings.civic_supplement_enabled", True, raising=False
        )
        assert algorithm_fingerprint() != before

    def test_degraded_evidence_policy_changes_the_fingerprint(self, monkeypatch):
        before = algorithm_fingerprint()
        monkeypatch.setattr(
            "config.settings.require_current_evidence", True, raising=False
        )
        assert algorithm_fingerprint() != before

    def test_a_ranking_weight_changes_the_fingerprint(self, monkeypatch):
        from ai.ranking_config import DEFAULT_CONFIG

        before = algorithm_fingerprint()
        monkeypatch.setattr(DEFAULT_CONFIG.weights, "oncokb", 0.41, raising=False)
        assert algorithm_fingerprint() != before, (
            "a weight moved and the fingerprint did not, so it is not "
            "identifying the algorithm"
        )


class TestItIdentifiesRulesNotEvidence:
    """The evidence snapshot belongs to evidence_provenance, not here.

    Folding the table's contents in would make the algorithm version churn
    every time an OncoKB dump refreshed, which answers neither question well:
    which rules ran, and which evidence they ran against.
    """

    def test_the_note_says_so(self):
        assert "evidence_provenance" in get_algorithm_version()["note"]

    def test_evidence_table_contents_are_not_in_the_fingerprint(self, monkeypatch):
        import services.oncokb_evidence as ev

        before = algorithm_fingerprint()
        patched = dict(ev._LEVEL_TABLE)
        patched[("MADEUPGENE", "V1M")] = {"madeupdrug": "LEVEL_1"}
        monkeypatch.setattr(ev, "_LEVEL_TABLE", patched, raising=False)
        assert algorithm_fingerprint() == before


class TestChangeControl:
    """The manual half. A silent behaviour change has to fail something.

    When this test fails, exactly one of two things is true: the algorithm
    changed and ALGORITHM_VERSION was not moved, or the fingerprint below is
    simply out of date. Both need a person; neither should pass quietly.
    """

    # Update together with ALGORITHM_VERSION, never on its own.
    #
    # This value must be identical in every process. It was not at first: the
    # ranking config holds six sets, Python randomises set iteration order per
    # process, and _plain fell through to str() for them, so three runs gave
    # three fingerprints. A version identifier that changes when nothing
    # changed is worse than none, because it trains everyone to update the
    # expected value without looking at why it moved.
    EXPECTED_FINGERPRINT = "f8d2d83050aa7a54"
    EXPECTED_VERSION = "1.0.0"

    def test_declared_version_has_not_drifted(self):
        assert ALGORITHM_VERSION == self.EXPECTED_VERSION

    def test_fingerprint_matches_the_declared_version(self):
        assert algorithm_fingerprint() == self.EXPECTED_FINGERPRINT, (
            "Ranking behaviour changed. If that was intended, move "
            "ALGORITHM_VERSION and update EXPECTED_FINGERPRINT together; if it "
            "was not, the change is unintended and should be reverted. "
            "REGULATORY_FRAMEWORK.md section 2.3."
        )


class TestPersistedOnTheResult:
    def test_result_model_has_the_column(self):
        from models.result import Result

        assert hasattr(Result, "algorithm_version")

    def test_the_column_is_nullable(self):
        """An older result must read as unrecorded, not as current rules."""
        from models.result import Result

        assert Result.__table__.c.algorithm_version.nullable is True

    def test_the_api_response_exposes_it(self):
        from schemas.responses import ResultsResponse

        assert "algorithm_version" in ResultsResponse.model_fields

    def test_the_response_defaults_to_none(self):
        """Not recorded and recorded-as-current must not look alike."""
        from schemas.responses import ResultsResponse

        assert ResultsResponse.model_fields["algorithm_version"].default is None
