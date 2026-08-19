"""What decides the order when the evidence does not.

risk_analysis.md F16. Every candidate carrying LEVEL_1 and nothing else scores
exactly 1.0000, because an absent evidence source has its weight redistributed
across the sources that are present. Six LEVEL_1 drugs therefore tie perfectly,
and the tie is broken alphabetically by drug name.

That is deterministic, which is worth something: the same input gives the same
report twice. But a top-three cut taken from a tied set is decided by spelling,
and the reader of that report sees a ranked list. Nothing in the output says
"these three were interchangeable and we picked the first three alphabetically".

These tests pin the current behaviour rather than assert it is correct, so that
changing it is a deliberate act with a visible diff. The clinical question of
what *should* break a tie is open and belongs with the human-factors work in
open action 6.
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

from ai.ranking import rank_candidates  # noqa: E402


def _c(name, **extra):
    base = {
        "drug_name": name,
        "oncokb_level": "LEVEL_1",
        "is_approved": True,
        "max_phase": 4,
    }
    base.update(extra)
    return base


class TestEqualEvidenceTies:
    def test_level_1_candidates_score_identically(self):
        pool = [_c(f"drug_{i}") for i in range(6)]
        scores = {round(c["rank_score"], 6) for c in rank_candidates(pool)}
        assert len(scores) == 1, "equal evidence must produce equal scores"

    def test_tie_is_broken_alphabetically(self):
        names = ["zanubrutinib", "afatinib", "midostaurin", "binimetinib"]
        ranked = rank_candidates([_c(n) for n in names])
        assert [c["drug_name"] for c in ranked] == sorted(names)

    def test_order_is_stable_regardless_of_input_order(self):
        """Determinism is the property worth keeping if the tiebreak changes."""
        names = ["zanubrutinib", "afatinib", "midostaurin", "binimetinib"]
        forward = [c["drug_name"] for c in rank_candidates([_c(n) for n in names])]
        backward = [
            c["drug_name"] for c in rank_candidates([_c(n) for n in reversed(names)])
        ]
        assert forward == backward

    def test_a_top3_cut_from_a_tied_set_is_spelling_not_evidence(self):
        """The property that matters clinically, stated as a test."""
        names = ["afatinib", "binimetinib", "cabozantinib", "trametinib", "ulixertinib"]
        top3 = [c["drug_name"] for c in rank_candidates([_c(n) for n in names])[:3]]
        assert top3 == ["afatinib", "binimetinib", "cabozantinib"]
        assert "trametinib" not in top3
        assert "ulixertinib" not in top3


class TestEvidenceStillOutranksNoEvidence:
    """The tie only applies among equals. Real evidence must still win."""

    def test_level_1_beats_a_target_association_only_candidate(self):
        pool = [
            _c("evidence_backed"),
            {
                "drug_name": "aaa_generic",  # alphabetically first on purpose
                "opentargets_score": 0.9,
                "is_approved": True,
                "max_phase": 4,
            },
        ]
        ranked = rank_candidates(pool)
        assert ranked[0]["drug_name"] == "evidence_backed", (
            "a drug with no actionability evidence must not outrank a LEVEL_1 "
            "drug merely by sorting earlier"
        )

    def test_a_generic_candidate_scores_below_level_1(self):
        ranked = rank_candidates(
            [
                _c("evidence_backed"),
                {
                    "drug_name": "generic",
                    "opentargets_score": 0.9,
                    "is_approved": True,
                    "max_phase": 4,
                },
            ]
        )
        by_name = {c["drug_name"]: c["rank_score"] for c in ranked}
        assert by_name["evidence_backed"] > by_name["generic"]


class TestAddingEvidenceIsNotPenalised:
    """Corroborating evidence must never lower a candidate's score.

    It currently can, slightly. A LEVEL_1 candidate alone scores 1.0000; the
    same candidate with an OpenTargets score of 0.9 scores 0.9969, because the
    OncoKB weight is no longer redistributed onto itself. The magnitude is small
    and usually clipped by the 1.0 cap, so this is xfail rather than a failing
    build: it records a known non-monotonicity without pretending it is urgent.
    """

    @pytest.mark.xfail(
        reason="known scoring non-monotonicity, ~0.3%, see risk_analysis.md F16",
        strict=False,
    )
    def test_adding_a_corroborating_source_does_not_reduce_the_score(self):
        alone = rank_candidates([_c("d")])[0]["rank_score"]
        with_ot = rank_candidates([_c("d", opentargets_score=0.9)])[0]["rank_score"]
        assert with_ot >= alone
