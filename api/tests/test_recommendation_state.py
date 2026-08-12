"""Tests for the three end states an analysis can reach.

Background: an empty drug list used to be indistinguishable from "we never
looked". The summary rendered it as "Top candidate drugs: currently being
analyzed", which reads as work still in progress even though the search had
finished and returned nothing.

That case stopped being hypothetical when the oncology-relevance gate started
removing non-cancer drugs from Tier 2 (services/oncology_atc.py). A patient who
previously saw digitoxin now sees nothing, and nothing is only an improvement
over digitoxin if it is clearly labelled as nothing.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from workers.ai_worker import _generate_summary  # noqa: E402


def _mut(gene: str) -> SimpleNamespace:
    return SimpleNamespace(gene=gene)


class TestSummaryStates:
    def test_no_targetable_mutation(self):
        summary = _generate_summary([_mut("TTN"), _mut("MUC16")], [], [])
        assert "found 2 genetic variation(s)" in summary
        assert "None of these mutations" in summary

    def test_candidates_found_lists_them(self):
        summary = _generate_summary(
            [_mut("EGFR")],
            [_mut("EGFR")],
            [{"drug_name": "osimertinib"}, {"drug_name": "erlotinib"}],
        )
        assert "osimertinib" in summary
        assert "erlotinib" in summary
        assert "currently being analyzed" not in summary

    def test_target_found_but_no_drug_says_so(self):
        """The state the oncology gate creates. Must not imply work in progress."""
        summary = _generate_summary([_mut("ARID1A")], [_mut("ARID1A")], [])
        assert "currently being analyzed" not in summary
        assert "completed the drug search" in summary
        assert "did not find an approved cancer therapy" in summary
        assert "ARID1A" in summary

    def test_empty_state_points_somewhere(self):
        """A dead end is not an acceptable answer. Name the remaining paths."""
        summary = _generate_summary([_mut("ARID1A")], [_mut("ARID1A")], [])
        assert "Clinical trials" in summary
        assert "custom drug discovery" in summary

    def test_excluded_drugs_are_named_in_the_empty_state(self):
        """If the reason the list is empty is that we filtered everything out,
        say what was filtered. Silently returning nothing hides the decision."""
        summary = _generate_summary(
            [_mut("ATP1A2")],
            [_mut("ATP1A2")],
            [],
            [{"drug_name": "digitoxin"}, {"drug_name": "deslanoside"}],
        )
        assert "2 drug(s)" in summary
        assert "digitoxin" in summary
        assert "not cancer treatments" in summary

    def test_excluded_is_optional(self):
        """Callers that predate the gate must keep working."""
        assert _generate_summary([_mut("EGFR")], [_mut("EGFR")], [])
        assert _generate_summary([_mut("EGFR")], [_mut("EGFR")], [], None)

    def test_no_em_dashes_in_patient_facing_text(self):
        """House style. These strings reach the patient report."""
        for summary in (
            _generate_summary([_mut("TTN")], [], []),
            _generate_summary([_mut("EGFR")], [_mut("EGFR")], []),
            _generate_summary([_mut("EGFR")], [_mut("EGFR")], [{"drug_name": "osimertinib"}]),
        ):
            assert "—" not in summary
            assert "–" not in summary
