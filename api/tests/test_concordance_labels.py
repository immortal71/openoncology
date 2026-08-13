"""Regression tests for the oncologist-concordance answer key.

The builder used to carry a DRUG_BIOMARKER_MAP that read each patient's gene off
the drug they were given, which made the benchmark a tautology: the pipeline was
asked which drug fits the gene, and the gene had been copied from that same
drug. These tests lock in the two properties that stop it coming back.

  1. The biomarker comes from the sequencing record and only from there. Change
     which drug a patient received and their gene must not move.
  2. A patient is labelled only when both sources have them.

scripts/detect_label_circularity.py is the statistical version of the same check
and runs against the real label file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILDER = _REPO_ROOT / "scripts" / "build_concordance_labels.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_concordance_labels", _BUILDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()


CLINICAL_HEADER = "cases.submitter_id\ttreatments.therapeutic_agents\n"


def _write_clinical_tsv(tmp_path: Path, name: str, rows: list[tuple[str, str]]) -> Path:
    path = tmp_path / name
    body = "".join(f"{patient}\t{agents}\n" for patient, agents in rows)
    path.write_text(CLINICAL_HEADER + body, encoding="utf-8")
    return path


def _write_biomarkers(tmp_path: Path, patients: dict[str, list[dict]], study_patient_ids: list[str]) -> Path:
    path = tmp_path / "biomarkers.json"
    path.write_text(
        json.dumps(
            {
                "source": "test fixture",
                "gene_panel": {"panel_id": "TEST", "n_genes": len(patients)},
                "studies": {
                    "TCGA-SKCM": {
                        "study_id": "skcm_tcga",
                        "patient_ids_in_study": study_patient_ids,
                    }
                },
                "patients": {"TCGA-SKCM": patients},
            }
        ),
        encoding="utf-8",
    )
    return path


def _alteration(gene: str, protein_change: str, alteration_type: str = "Mutation") -> dict:
    return {
        "gene": gene,
        "protein_change": protein_change,
        "alteration_type": alteration_type,
    }


def test_drug_biomarker_map_is_gone():
    """The map that derived gene from drug must not exist in any form."""
    assert not hasattr(builder, "DRUG_BIOMARKER_MAP")

    source = _BUILDER.read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    _, _, after_docstring = code.partition('"""')
    _, _, code_body = after_docstring.partition('"""')
    assert "DRUG_BIOMARKER_MAP" not in code_body


def test_biomarker_does_not_move_when_the_drug_changes(tmp_path):
    """The decisive property: the gene is a function of sequencing, not treatment.

    Two patients with identical sequencing records but completely different
    treatment must receive the same gene. Under the old builder, the trastuzumab
    patient would have been labelled ERBB2 and the vemurafenib patient BRAF.
    """
    biomarkers = _write_biomarkers(
        tmp_path,
        {
            "TCGA-AA-0001": [_alteration("PTEN", "R130Q")],
            "TCGA-AA-0002": [_alteration("PTEN", "R130Q")],
        },
        ["TCGA-AA-0001", "TCGA-AA-0002"],
    )
    tsv = _write_clinical_tsv(
        tmp_path,
        "clinical.tsv",
        [("TCGA-AA-0001", "trastuzumab"), ("TCGA-AA-0002", "vemurafenib")],
    )

    payload = builder.build_labels([tsv], biomarkers)
    by_patient = {row["patient_id"]: row for row in payload["labels"]}

    assert by_patient["TCGA-AA-0001"]["gene"] == "PTEN"
    assert by_patient["TCGA-AA-0002"]["gene"] == "PTEN"
    assert by_patient["TCGA-AA-0001"]["variant"] == "R130Q"
    assert by_patient["TCGA-AA-0002"]["oncologist_recommended_drugs"] == ["vemurafenib"]


def test_patient_missing_either_source_is_dropped(tmp_path):
    biomarkers = _write_biomarkers(
        tmp_path,
        {
            "TCGA-AA-0001": [_alteration("KRAS", "G12C")],
            "TCGA-AA-0003": [_alteration("EGFR", "L858R")],
        },
        ["TCGA-AA-0001", "TCGA-AA-0002", "TCGA-AA-0003"],
    )
    tsv = _write_clinical_tsv(
        tmp_path,
        "clinical.tsv",
        [
            ("TCGA-AA-0001", "cisplatin"),
            ("TCGA-AA-0002", "carboplatin"),  # sequenced, nothing on the panel
            ("TCGA-AA-0004", "paclitaxel"),  # never sequenced
            ("TCGA-AA-0003", "'--"),  # sequenced, no recorded agent
        ],
    )

    payload = builder.build_labels([tsv], biomarkers)

    assert [row["patient_id"] for row in payload["labels"]] == ["TCGA-AA-0001"]

    denominator = payload["denominator"]
    assert denominator["patients_with_both_scored"] == 1
    assert denominator["dropped_drug_and_sequenced_but_no_panel_alteration"] == 1
    assert denominator["dropped_drug_but_not_sequenced"] == 1
    # TCGA-AA-0003 has a sequencing record but no agent, so it never enters the
    # drug side at all.
    assert denominator["patients_with_a_recorded_drug"] == 3


def test_all_of_a_patients_alterations_are_kept(tmp_path):
    """The primary gene is a convenience for single-gene callers, not the record."""
    biomarkers = _write_biomarkers(
        tmp_path,
        {
            "TCGA-AA-0001": [
                _alteration("TP53", "R175H"),
                _alteration("ERBB2", "AMPLIFICATION", "Amplification"),
            ],
            "TCGA-AA-0002": [_alteration("TP53", "R248W")],
        },
        ["TCGA-AA-0001", "TCGA-AA-0002"],
    )
    tsv = _write_clinical_tsv(
        tmp_path,
        "clinical.tsv",
        [("TCGA-AA-0001", "trastuzumab"), ("TCGA-AA-0002", "fluorouracil")],
    )

    payload = builder.build_labels([tsv], biomarkers)
    row = next(r for r in payload["labels"] if r["patient_id"] == "TCGA-AA-0001")

    assert {b["gene"] for b in row["biomarkers"]} == {"TP53", "ERBB2"}
    # TP53 is altered in both patients and ERBB2 in one, so cohort recurrence
    # picks TP53. The trastuzumab patient is not steered to ERBB2 by their drug.
    assert row["gene"] == "TP53"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("'Cisplatin, Paclitaxel", ["Cisplatin", "Paclitaxel"]),
        ("'--", []),
        ("Clinical Trial Agent", []),
    ],
)
def test_agent_parsing_is_unchanged(tmp_path, raw, expected):
    biomarkers = _write_biomarkers(
        tmp_path, {"TCGA-AA-0001": [_alteration("BRAF", "V600E")]}, ["TCGA-AA-0001"]
    )
    tsv = _write_clinical_tsv(tmp_path, "clinical.tsv", [("TCGA-AA-0001", raw)])

    payload = builder.build_labels([tsv], biomarkers)

    if expected:
        assert payload["labels"][0]["oncologist_recommended_drugs"] == expected
    else:
        assert payload["labels"] == []
