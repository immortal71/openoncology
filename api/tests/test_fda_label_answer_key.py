"""A label that excludes a biomarker must not become a pairing that requires it.

scripts/build_fda_label_answer_key.py extracts biomarker-to-drug pairs from FDA
label INDICATIONS AND USAGE text, to give this repository an answer key that is
independent of every source the recommendation path reads.

Its first build was wrong in a way that would have scored the engine backwards.
Four drugs indicated for HER2-*negative* disease came out paired with ERBB2:

    everolimus, palbociclib, ribociclib, talazoparib

Each of those labels names HER2 only to exclude patients who carry it. Recording
that as a positive pairing would mark the engine wrong for correctly declining
to recommend a HER2 drug, which is worse than a missing pair: it inverts the
grading on exactly the cases the key exists to grade.

These tests pin the negation handling, because the failure is silent. A key with
inverted pairings still produces a plausible-looking percentage.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "build_fda_label_answer_key.py"


def _module():
    spec = importlib.util.spec_from_file_location("_fda_key", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def keybuilder():
    return _module()


class TestNegatedBiomarkersAreExcluded:
    """The defect that motivated this file."""

    @pytest.mark.parametrize(
        "sentence",
        [
            "HR-positive, human epidermal growth factor receptor 2 (HER2)-negative "
            "advanced or metastatic breast cancer",
            "HER2 (ERBB2)-negative disease",
            "HER2-negative locally advanced breast cancer",
            "patients with non-ERBB2 amplified tumors",
            "patients without EGFR mutations",
            "BRAF wild-type melanoma",
            "tumors that are EGFR not detected",
        ],
    )
    def test_exclusion_wording_yields_no_pairing(self, keybuilder, sentence):
        assert keybuilder._genes_in(sentence) == set(), (
            f"negated biomarker leaked into the key: {sentence!r}"
        )

    def test_the_four_real_labels_that_broke_it(self, keybuilder):
        """Wording taken from the actual labels that produced the bad pairs."""
        talazoparib = (
            "for the treatment of adult patients with deleterious or suspected "
            "deleterious germline BRCA-mutated (gBRCAm) HER2-negative locally "
            "advanced or metastatic breast cancer"
        )
        genes = keybuilder._genes_in(talazoparib)
        assert "ERBB2" not in genes, "HER2-negative must not pair with ERBB2"


class TestPositiveBiomarkersSurvive:
    """Negation handling must not silence the pairings the key is built for."""

    @pytest.mark.parametrize(
        "sentence,gene",
        [
            ("HER2-positive metastatic breast cancer", "ERBB2"),
            ("tumors have EGFR exon 19 deletions or exon 21 L858R mutations", "EGFR"),
            ("ALK-positive non-small cell lung cancer", "ALK"),
            ("BRAF V600E mutation-positive melanoma", "BRAF"),
            ("KRAS G12C-mutated locally advanced NSCLC", "KRAS"),
            ("metastatic NSCLC with MET exon 14 skipping alterations", "MET"),
        ],
    )
    def test_selection_criteria_are_kept(self, keybuilder, sentence, gene):
        assert gene in keybuilder._genes_in(sentence)

    def test_a_sentence_naming_one_gene_both_ways_keeps_it(self, keybuilder):
        """Positive mention anywhere outweighs a negated one elsewhere."""
        sentence = (
            "EGFR-positive tumors, excluding patients without EGFR expression"
        )
        assert "EGFR" in keybuilder._genes_in(sentence)


class TestAmbiguousSymbolsNeedAQualifier:
    """MET and AR are ordinary words as well as gene symbols."""

    def test_met_requires_a_qualifier(self, keybuilder):
        assert "MET" not in keybuilder._genes_in("patients who have MET the criteria")

    def test_met_with_exon_14_is_kept(self, keybuilder):
        assert "MET" in keybuilder._genes_in("MET exon 14 skipping alterations")

    def test_ar_requires_androgen_receptor(self, keybuilder):
        assert "AR" not in keybuilder._genes_in("AR is not a gene symbol here")


class TestAliasing:
    def test_her2_maps_to_erbb2(self, keybuilder):
        assert "ERBB2" in keybuilder._genes_in("HER2-positive breast cancer")
        assert "HER2" not in keybuilder._genes_in("HER2-positive breast cancer")
