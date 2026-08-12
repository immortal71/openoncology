"""Tests for the Tier 2 oncology-relevance gate (services/oncology_atc.py).

These pin the exact drugs the pipeline previously recommended to cancer
patients through Tier 2 repurposing, taken from the 2026-07-28 concordance
pilot's real output.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.oncology_atc import (  # noqa: E402
    partition_candidates,
    should_exclude,
)

# Real Tier 2 output from the pilot. Cardiac glycosides, a beta blocker,
# vitamin C and BPH drugs, all shown as ranked cancer treatment candidates.
NON_ONCOLOGY = [
    "ACETYLDIGITOXIN", "DESLANOSIDE", "DIGITOXIN", "ATENOLOL",
    "ASCORBIC ACID", "ALFUZOSIN", "DOXAZOSIN",
]

ONCOLOGY = [
    "IMATINIB", "OLAPARIB", "TAMOXIFEN", "SUNITINIB", "PAZOPANIB",
    "CAPMATINIB", "SORAFENIB", "TRASTUZUMAB", "EVEROLIMUS", "OSIMERTINIB",
]


class TestOncologyGate:
    def test_non_oncology_drugs_are_excluded(self):
        for drug in NON_ONCOLOGY:
            assert should_exclude(drug, allow_network=False), drug

    def test_real_oncology_drugs_are_never_excluded(self):
        """The property that matters most. A filter that drops trastuzumab is
        worse than the noise it removes."""
        for drug in ONCOLOGY:
            assert not should_exclude(drug, allow_network=False), drug

    def test_unknown_drug_is_kept_not_dropped(self):
        """Unknown is not evidence. A drug absent from the ATC cache, or a
        failed lookup, must degrade to current behaviour rather than delete a
        potentially real therapy."""
        assert not should_exclude("NOT-A-REAL-DRUG-XYZ", allow_network=False)
        assert not should_exclude("", allow_network=False)

    def test_partition_separates_without_losing_candidates(self):
        candidates = [{"drug_name": n} for n in ONCOLOGY + NON_ONCOLOGY]
        keep, dropped = partition_candidates(candidates, allow_network=False)
        assert len(keep) + len(dropped) == len(candidates)
        assert {c["drug_name"] for c in dropped} == set(NON_ONCOLOGY)
        assert {c["drug_name"] for c in keep} == set(ONCOLOGY)

    def test_partition_annotates_candidates(self):
        keep, dropped = partition_candidates(
            [{"drug_name": "IMATINIB"}, {"drug_name": "ATENOLOL"}],
            allow_network=False,
        )
        assert keep[0]["oncology_relevant"] is True
        assert any(c.startswith("L01") for c in keep[0]["atc_codes"])
        assert dropped[0]["oncology_relevant"] is False
