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
    parent_name,
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

# The same pilot output as DGIdb/OpenTargets actually spelled it. The names
# above are the parent molecules; these salt and formulation forms missed the
# cache, came back unknown, and were kept.
NON_ONCOLOGY_SALT_FORMS = [
    "ALFUZOSIN HYDROCHLORIDE", "DOXAZOSIN MESYLATE", "BALSALAZIDE DISODIUM",
    "FENOFIBRATE MICRONIZED",
]

ONCOLOGY_SALT_FORMS = [
    "AFATINIB DIMALEATE", "ALECTINIB HYDROCHLORIDE", "DOXORUBICIN HYDROCHLORIDE",
    "DASATINIB ANHYDROUS", "COPANLISIB HYDROCHLORIDE", "SUNITINIB MALATE",
    "SORAFENIB TOSYLATE",
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

    def test_salt_forms_of_non_oncology_drugs_are_excluded(self):
        for drug in NON_ONCOLOGY_SALT_FORMS:
            assert should_exclude(drug, allow_network=False), drug

    def test_salt_forms_of_oncology_drugs_are_classified_and_kept(self):
        keep, dropped = partition_candidates(
            [{"drug_name": n} for n in ONCOLOGY_SALT_FORMS], allow_network=False,
        )
        assert dropped == []
        for candidate in keep:
            assert candidate["oncology_relevant"] is True, candidate["drug_name"]

    def test_parent_name_strips_only_trailing_salt_words(self):
        assert parent_name("ALFUZOSIN HYDROCHLORIDE") == "alfuzosin"
        assert parent_name("Sorafenib  Tosylate") == "sorafenib"
        assert parent_name("ASCORBIC ACID") == "ascorbic acid"
        assert parent_name("GLYCEROL PHENYLBUTYRATE") == "glycerol phenylbutyrate"
        assert parent_name("SODIUM") == "sodium"
        assert parent_name("SODIUM THIOSULFATE") == "sodium thiosulfate"

    def test_unknown_parent_stays_unknown(self):
        assert not should_exclude("NOT-A-REAL-DRUG-XYZ HYDROCHLORIDE", allow_network=False)

    def test_partition_annotates_candidates(self):
        keep, dropped = partition_candidates(
            [{"drug_name": "IMATINIB"}, {"drug_name": "ATENOLOL"}],
            allow_network=False,
        )
        assert keep[0]["oncology_relevant"] is True
        assert any(c.startswith("L01") for c in keep[0]["atc_codes"])
        assert dropped[0]["oncology_relevant"] is False


class TestCytotoxicExclusion:
    """OO-28: classical chemotherapy is not a mutation match.

    In the 2026-07-28 pilot every TP53 patient was offered these three from a
    DGIdb gene interaction, and 7 of the pilot's 8 hits were these drugs
    coinciding with chemotherapy the patient happened to receive.
    """

    TP53_PILOT_PICKS = ["CISPLATIN", "DOXORUBICIN HYDROCHLORIDE", "CARBOPLATIN"]
    TARGETED = ["OLAPARIB", "SUNITINIB MALATE", "TRASTUZUMAB", "TAMOXIFEN", "AFATINIB DIMALEATE"]

    def test_tp53_pilot_chemotherapy_is_dropped_when_asked(self):
        kept, dropped = partition_candidates(
            [{"drug_name": d} for d in self.TP53_PILOT_PICKS],
            allow_network=False, drop_cytotoxic=True,
        )
        assert kept == []
        assert {d["drug_name"] for d in dropped} == set(self.TP53_PILOT_PICKS)
        assert all("cytotoxic" in d["indication_exclusion"] for d in dropped)

    def test_targeted_and_endocrine_drugs_are_kept(self):
        kept, dropped = partition_candidates(
            [{"drug_name": d} for d in self.TARGETED],
            allow_network=False, drop_cytotoxic=True,
        )
        assert dropped == []

    def test_chemotherapy_kept_without_the_flag(self):
        kept, dropped = partition_candidates(
            [{"drug_name": d} for d in self.TP53_PILOT_PICKS], allow_network=False,
        )
        assert dropped == []

    def test_chemotherapy_with_curated_variant_evidence_is_kept(self):
        kept, dropped = partition_candidates(
            [{"drug_name": "CISPLATIN", "evidence_sources": ["CIViC", "ChEMBL"]}],
            allow_network=False, drop_cytotoxic=True,
        )
        assert [d["drug_name"] for d in kept] == ["CISPLATIN"]

    def test_unknown_drug_is_not_treated_as_chemotherapy(self):
        kept, _ = partition_candidates(
            [{"drug_name": "NOT A REAL DRUG XYZ"}], allow_network=False, drop_cytotoxic=True,
        )
        assert len(kept) == 1
