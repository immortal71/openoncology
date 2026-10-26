"""Standard-of-care options by cancer type (OO-28).

Pinned to the 2026-07-28 concordance pilot: the drugs recorded for its kidney
and prostate patients are standard care for those cancers and are not chosen
by a mutation, so the mutation ranker could never match them.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.standard_of_care import REVIEW_STATUS, drug_names, options_for, report  # noqa: E402


def test_kidney_cancer_lists_the_pilot_drugs():
    names = drug_names("Renal Cell Carcinoma")
    for drug in ("sunitinib", "sorafenib", "pazopanib", "temsirolimus", "everolimus", "bevacizumab"):
        assert drug in names, drug


def test_prostate_cancer_lists_androgen_deprivation():
    names = drug_names("Prostate Cancer")
    for drug in ("leuprolide", "goserelin", "bicalutamide", "abiraterone"):
        assert drug in names, drug


def test_biomarker_conditional_options_say_so():
    her2 = [r for r in options_for("Breast Invasive Carcinoma") if "trastuzumab" in r.drugs]
    assert her2 and all(r.requires for r in her2)
    assert "trastuzumab" not in drug_names("Breast Cancer", include_conditional=False)


def test_belzutifan_is_later_line_only():
    belz = [r for r in options_for("Kidney Renal Clear Cell Carcinoma") if r.drugs == ("belzutifan",)]
    assert belz and belz[0].line == "later-line"


def test_unknown_cancer_type_returns_nothing():
    assert options_for("Something Unheard Of") == []
    assert options_for(None) == []


def test_report_is_labelled_as_not_mutation_based():
    r = report("Glioblastoma Multiforme")
    assert r["cancer_context"] == "GLIOMA"
    assert "not selected by the tumour's mutations" in r["basis"]
    assert r["review_status"] == REVIEW_STATUS
    assert any(o["regimen"] == "temozolomide" for o in r["options"])


def test_gist_is_not_given_gastric_cancer_chemotherapy():
    assert options_for("Gastrointestinal stromal tumor of stomach") == []
