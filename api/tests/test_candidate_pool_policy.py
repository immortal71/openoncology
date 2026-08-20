"""Which candidates are eligible to be ranked, and the switch that decides.

docs/BENCHMARK_NCI_MATCH.md measured two pool models. `tier2` ranks everything
the repurposing sources returned; `evidence_first` ranks only the actionability
table's answer when it has one. On the FDA-label answer key, independent of
every source this engine reads, evidence_first scored 15.1 points higher on
Precision@3 with 7 wins to 0.

The default was flipped to `evidence_first` on 2026-08-19 as a maintainer
decision on that evidence. These tests pin both branches, every fallback path,
and the default itself, so the behaviour is predictable in either setting and the
default cannot drift unnoticed.

The fallback cases matter most. A policy that can empty the candidate list is
worse than the imprecision it was introduced to fix, so an empty table, a
resistance-only table, and a failed lookup all have to return the repurposing
pool untouched.
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

import workers.ai_worker as w  # noqa: E402

_POOL = [
    {"drug_name": "generic_a", "opentargets_score": 0.9, "smiles": "CCO"},
    {"drug_name": "osimertinib", "opentargets_score": 0.7, "smiles": "CCN", "binding_score": 0.8},
    {"drug_name": "generic_b", "opentargets_score": 0.6},
]


@pytest.fixture
def policy(monkeypatch):
    def _set(value):
        monkeypatch.setattr("config.settings.candidate_pool_policy", value, raising=False)

    return _set


@pytest.fixture
def table(monkeypatch):
    def _set(mapping):
        monkeypatch.setattr(
            "services.oncokb_evidence.get_all_drugs_for_variant_live",
            lambda *a, **k: dict(mapping),
            raising=False,
        )

    return _set


class TestDefault:
    def test_setting_defaults_to_evidence_first(self):
        """Flipped 2026-08-19. Pinned so the change stays deliberate."""
        from config import Settings

        assert Settings().candidate_pool_policy == "evidence_first"

    def test_tier2_returns_the_pool_untouched(self, policy, table):
        policy("tier2")
        table({"osimertinib": "LEVEL_1"})
        assert w._apply_candidate_pool_policy(list(_POOL), "EGFR", "L858R") == _POOL


class TestEvidenceFirst:
    def test_table_decides_membership(self, policy, table):
        policy("evidence_first")
        table({"osimertinib": "LEVEL_1", "erlotinib": "LEVEL_1"})
        out = w._apply_candidate_pool_policy(list(_POOL), "EGFR", "L858R")
        names = {d["drug_name"] for d in out}
        assert names == {"osimertinib", "erlotinib"}
        assert "generic_a" not in names

    def test_enrichment_is_preserved_for_members(self, policy, table):
        """Table membership must not throw away structural data already fetched."""
        policy("evidence_first")
        table({"osimertinib": "LEVEL_1"})
        out = w._apply_candidate_pool_policy(list(_POOL), "EGFR", "L858R")
        osi = next(d for d in out if d["drug_name"] == "osimertinib")
        assert osi["smiles"] == "CCN"
        assert osi["binding_score"] == 0.8
        assert osi["oncokb_level"] == "LEVEL_1"

    def test_table_only_drugs_are_marked_approved(self, policy, table):
        policy("evidence_first")
        table({"erlotinib": "LEVEL_1"})
        out = w._apply_candidate_pool_policy(list(_POOL), "EGFR", "L858R")
        erl = next(d for d in out if d["drug_name"] == "erlotinib")
        assert erl["is_approved"] is True
        assert erl["max_phase"] == 4

    def test_resistance_markers_never_become_candidates(self, policy, table):
        policy("evidence_first")
        table({"osimertinib": "LEVEL_1", "gefitinib": "LEVEL_R1"})
        out = w._apply_candidate_pool_policy(list(_POOL), "EGFR", "T790M")
        assert {d["drug_name"] for d in out} == {"osimertinib"}


class TestFallingBackIsSafe:
    """The policy must never be able to empty the pool."""

    def test_empty_table_keeps_the_repurposing_pool(self, policy, table):
        policy("evidence_first")
        table({})
        assert w._apply_candidate_pool_policy(list(_POOL), "NF2", None) == _POOL

    def test_table_of_only_resistance_keeps_the_pool(self, policy, table):
        policy("evidence_first")
        table({"gefitinib": "LEVEL_R1"})
        assert w._apply_candidate_pool_policy(list(_POOL), "EGFR", "T790M") == _POOL

    def test_lookup_failure_keeps_the_pool(self, policy, monkeypatch):
        policy("evidence_first")

        def _boom(*a, **k):
            raise RuntimeError("evidence source down")

        monkeypatch.setattr(
            "services.oncokb_evidence.get_all_drugs_for_variant_live",
            _boom,
            raising=False,
        )
        assert w._apply_candidate_pool_policy(list(_POOL), "EGFR", "L858R") == _POOL

    def test_an_empty_incoming_pool_is_handled(self, policy, table):
        policy("evidence_first")
        table({"osimertinib": "LEVEL_1"})
        out = w._apply_candidate_pool_policy([], "EGFR", "L858R")
        assert [d["drug_name"] for d in out] == ["osimertinib"]
