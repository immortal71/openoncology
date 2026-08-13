"""Notation robustness: the same finding, written the way different sources
write it, must reach the same evidence.

WHY THIS EXISTS SEPARATELY
--------------------------
The coverage benchmark cannot detect this class of bug. Its pinned cohort is
eight genes of plain point-mutation notation, with no fusions, no
amplifications, no legacy gene symbols and no trade names, so a normalisation
regression leaves its coverage number completely unchanged. Every notation
failure found so far was silent: an unrecognised string is indistinguishable
from a finding with no evidence.

Each entry below is an equivalence class. One canonical form, then the
spellings that real sources actually emit for the same finding. The test
asserts they all return identical evidence, not merely non-empty evidence,
because returning the wrong bucket is worse than returning nothing.

Adding a case is one line. When a lab sends notation this does not cover, put
it here first and watch it fail before fixing the normaliser.

Every spelling in this file returned nothing at all before the fixes it
guards; the history is in the audit scripts under scripts/.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.oncokb_evidence import (  # noqa: E402
    _normalise_cancer_context,
    get_all_drugs_for_variant,
)

# (label, (gene, alteration), [(gene, alteration), ...equivalent spellings])
EQUIVALENCE_CLASSES: list[tuple[str, tuple[str, str], list[tuple[str, str]]]] = [
    # ── Fusion delimiters. HGVS/ISCN recommend "::", which is what labs are
    # migrating to; STAR-Fusion emits "--".
    ("ALK fusion", ("ALK", "EML4-ALK"),
     [("ALK", "EML4::ALK"), ("ALK", "EML4--ALK")]),
    ("ROS1 fusion", ("ROS1", "CD74-ROS1"), [("ROS1", "CD74::ROS1")]),
    ("RET fusion", ("RET", "KIF5B-RET"), [("RET", "KIF5B::RET")]),
    ("NTRK3 fusion", ("NTRK3", "ETV6-NTRK3"), [("NTRK3", "ETV6::NTRK3")]),
    ("APL fusion", ("RARA", "PML-RARA"), [("RARA", "PML::RARA")]),

    # ── Copy number. cBioPortal exports HOMDEL and labels it "Deep Deletion";
    # pathology reports say "amplified" rather than "Amplification".
    ("ERBB2 amplification", ("ERBB2", "Amplification"),
     [("ERBB2", "amplified"), ("ERBB2", "AMP"), ("ERBB2", "high level amplification")]),
    ("MET amplification", ("MET", "Amplification"), [("MET", "amplified")]),
    ("CDKN2A deep deletion", ("CDKN2A", "homozygous deletion"),
     [("CDKN2A", "HOMDEL"), ("CDKN2A", "deep deletion")]),

    # ── Gene symbols as clinicians write them.
    ("HER2 as ERBB2", ("ERBB2", "Amplification"),
     [("HER2", "Amplification"), ("HER-2", "Amplification"),
      ("HER2/neu", "Amplification")]),
    ("c-KIT as KIT", ("KIT", "V559D"), [("c-KIT", "V559D"), ("CD117", "V559D")]),
    ("c-MET as MET", ("MET", "exon 14 skipping"), [("c-MET", "exon 14 skipping")]),
    ("K-RAS as KRAS", ("KRAS", "G12C"), [("K-RAS", "G12C")]),
    ("p16 as CDKN2A", ("CDKN2A", "homozygous deletion"),
     [("p16", "homozygous deletion"), ("INK4A", "homozygous deletion")]),

    # ── Exon-level classes expressed as specific HGVS.
    ("EGFR exon 19 deletion", ("EGFR", "Exon19del"),
     [("EGFR", "E746_A750del"), ("EGFR", "p.Glu746_Ala750del"),
      ("EGFR", "T751_E758del")]),
    ("EGFR exon 20 insertion", ("EGFR", "D770_N771insSVD"),
     [("EGFR", "A767_V769dup"), ("EGFR", "H773dup"),
      ("EGFR", "p.Asp770_Asn771insSerValAsp")]),
    ("KIT exon 11 mutation", ("KIT", "EXON11MUT"),
     [("KIT", "V559D"), ("KIT", "L576P"), ("KIT", "W557R")]),

    # ── Loss of function written as real HGVS rather than a bucket name.
    ("BRCA2 truncating", ("BRCA2", "TRUNCATING"),
     [("BRCA2", "S1982fs"), ("BRCA2", "K3326*")]),

    # ── Immunohistochemistry phrasing.
    ("MLH1 loss of expression", ("MLH1", "loss of expression"),
     [("MLH1", "absent"), ("MLH1", "deficient"), ("MLH1", "IHC loss")]),
]


@pytest.mark.parametrize(
    "label,canonical,variants",
    EQUIVALENCE_CLASSES,
    ids=[c[0] for c in EQUIVALENCE_CLASSES],
)
def test_equivalent_notation_returns_identical_evidence(label, canonical, variants):
    gene, alteration = canonical
    expected = get_all_drugs_for_variant(gene, alteration) or {}
    assert expected, (
        f"{label}: canonical form {gene} {alteration} has no evidence, so this "
        f"class cannot be compared. Fix the case or the curation, do not delete "
        f"the assertion."
    )
    for variant_gene, variant_alt in variants:
        got = get_all_drugs_for_variant(variant_gene, variant_alt) or {}
        assert got == expected, (
            f"{label}: {variant_gene} {variant_alt} resolved to {sorted(got)} "
            f"but {gene} {alteration} resolves to {sorted(expected)}"
        )


# Trade names, checked through the whole-variant lookup rather than just the
# level lookup, since that is the path a submitted report takes.
DRUG_EQUIVALENCE = [
    ("Herceptin", "trastuzumab", "ERBB2", "Amplification"),
    ("Tagrisso", "osimertinib", "EGFR", "T790M"),
    ("Gleevec", "imatinib", "KIT", "EXON11MUT"),
    ("Zelboraf", "vemurafenib", "BRAF", "V600E"),
    ("Lumakras", "sotorasib", "KRAS", "G12C"),
    ("Lynparza", "olaparib", "BRCA1", "S1982fs"),
]


@pytest.mark.parametrize(
    "brand,inn,gene,alteration", DRUG_EQUIVALENCE,
    ids=[d[0] for d in DRUG_EQUIVALENCE],
)
def test_trade_name_matches_inn(brand, inn, gene, alteration):
    from services.oncokb_evidence import lookup_oncokb_level
    expected = lookup_oncokb_level(gene, alteration, inn)
    assert expected is not None, f"{inn} has no level for {gene} {alteration}"
    assert lookup_oncokb_level(gene, alteration, brand) == expected


# Cancer context. Registries record the histology, not the umbrella term.
CONTEXT_EQUIVALENCE = [
    ("NSCLC", ["Lung adenocarcinoma", "Lung squamous cell carcinoma", "LUAD",
               "LUSC", "Non-small cell lung cancer"]),
    ("SCLC", ["Small cell lung cancer", "Small cell lung carcinoma",
              "Lung small cell carcinoma", "SCLC"]),
    ("BREAST", ["Breast invasive carcinoma", "TNBC",
                "Triple-negative breast cancer"]),
    ("GASTRIC", ["Stomach adenocarcinoma", "Gastric adenocarcinoma"]),
    ("COLORECTAL", ["Colorectal adenocarcinoma", "Colon adenocarcinoma",
                    "Rectal adenocarcinoma", "CRC"]),
    ("GLIOMA", ["Glioblastoma multiforme", "GBM"]),
]


@pytest.mark.parametrize(
    "expected,spellings", CONTEXT_EQUIVALENCE,
    ids=[c[0] for c in CONTEXT_EQUIVALENCE],
)
def test_cancer_context_spellings(expected, spellings):
    for spelling in spellings:
        assert _normalise_cancer_context(spelling) == expected, spelling


def test_small_cell_never_resolves_to_nsclc():
    """Kept as its own test because it is a safety property, not a coverage
    one. SCLC has different treatment, so routing it to NSCLC would be an
    actively wrong answer rather than a missing one."""
    for spelling in ["Small cell lung cancer", "Small cell lung carcinoma",
                     "Lung small cell carcinoma", "SCLC"]:
        assert _normalise_cancer_context(spelling) != "NSCLC", spelling


# Findings that must NOT collapse into each other. A normaliser that is too
# aggressive produces a wrong answer, which is worse than the silence it was
# written to fix.
MUST_STAY_DISTINCT = [
    ("low-level gain is not amplification", ("ERBB2", "gain"), ("ERBB2", "Amplification")),
    ("copy number gain is not amplification", ("MET", "copy number gain"), ("MET", "Amplification")),
    ("T790M is not an exon 20 insertion", ("EGFR", "T790M"), ("EGFR", "D770_N771insSVD")),
    ("C797S is not an exon 20 insertion", ("EGFR", "C797S"), ("EGFR", "D770_N771insSVD")),
    ("KIT D816V is not an exon 11 mutation", ("KIT", "D816V"), ("KIT", "EXON11MUT")),
    ("MET D1010A is not exon 14 skipping", ("MET", "D1010A"), ("MET", "X1010_splice")),
]


@pytest.mark.parametrize(
    "label,probe,must_differ_from", MUST_STAY_DISTINCT,
    ids=[c[0] for c in MUST_STAY_DISTINCT],
)
def test_distinct_findings_do_not_collapse(label, probe, must_differ_from):
    probe_drugs = get_all_drugs_for_variant(*probe) or {}
    other_drugs = get_all_drugs_for_variant(*must_differ_from) or {}
    assert other_drugs, f"{label}: comparison target has no evidence"
    assert probe_drugs != other_drugs, label


def test_resistance_annotations_survive_normalisation():
    """Resistance levels are the most dangerous thing to lose, since dropping
    them turns a contraindication into a recommendation."""
    for gene, alteration in [("EGFR", "T790M"), ("EGFR", "C797S"), ("KIT", "D816V")]:
        levels = {str(v) for v in (get_all_drugs_for_variant(gene, alteration) or {}).values()}
        assert any(level.startswith("LEVEL_R") for level in levels), (
            f"{gene} {alteration} lost its resistance annotation"
        )
