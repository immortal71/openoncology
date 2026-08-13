"""Build the oncologist-concordance answer key from two independent sources.

WHAT WAS WRONG BEFORE
---------------------
This script used to carry a DRUG_BIOMARKER_MAP that read each patient's gene off
the drug they were given: trastuzumab meant "ERBB2 Amplified", vemurafenib meant
"BRAF V600E", and so on. No sequencing record was consulted. The benchmark then
asked OpenOncology which drug it would recommend for that gene and scored the
answer against the drug the gene had just been derived from, which is the same
question in both directions. 100% concordance was structurally guaranteed; no
other result was reachable.

The give-away was visible in the labels themselves. Zoledronic acid is a
bisphosphonate given for skeletal events, and it mapped to ERBB2 in all four of
its patients. Cisplatin mapped to EGFR in all eight. Cytotoxics and supportive
care are chosen without reference to any biomarker, so in measured data their
patients carry a spread of genes. A perfect mapping meant the gene had been
copied off a co-administered targeted agent.

HOW IT WORKS NOW
----------------
Two sources that cannot see each other:

  biomarker  <- the patient's own cBioPortal sequencing record (mutations and
                GISTIC copy-number calls), fetched by
                scripts/fetch_concordance_biomarkers.py
  drug       <- the therapeutic agents recorded on the patient's GDC clinical
                row, read from the scripts/clinical*.tsv exports

They are joined on patient id and nothing else. No drug influences which
biomarker a patient gets, and no biomarker influences which drug. A patient is
labelled only if both sources have them, and that denominator is printed rather
than buried, because it is much smaller than the number of patients with a drug.

scripts/detect_label_circularity.py is the regression test for this property and
exits non-zero if a future edit reintroduces derivation.

Usage:
    python scripts/fetch_concordance_biomarkers.py     # refresh the biomarker side
    python scripts/build_concordance_labels.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXCLUDED_AGENTS = {
    "",
    "--",
    "clinical trial agent",
}

DEFAULT_INPUT_FILES = [
    "scripts/clinical.tsv",
    "scripts/clinical (1).tsv",
    "scripts/clinical (2).tsv",
    "scripts/clinical (3).tsv",
    "scripts/clinical (4).tsv",
]

COHORT_BY_FILE = {
    "clinical.tsv": "TCGA-SKCM",
    "clinical (1).tsv": "TCGA-LUAD",
    "clinical (2).tsv": "TCGA-BRCA",
    "clinical (3).tsv": "TCGA-COAD",
    "clinical (4).tsv": "TCGA-GBM",
}

DEFAULT_BIOMARKERS_JSON = "scripts/concordance_biomarkers.json"

# TCGA project code to the disease name the pipeline expects. This is study
# metadata from the TCGA project descriptions, not a clinical claim, and it is
# the same mapping scripts/concordance_pilot_run_pipeline.py already uses.
CANCER_TYPE_BY_COHORT = {
    "TCGA-SKCM": "Melanoma",
    "TCGA-LUAD": "Non-Small Cell Lung Cancer",
    "TCGA-BRCA": "Breast Cancer",
    "TCGA-COAD": "Colorectal Cancer",
    "TCGA-GBM": "Glioblastoma",
}


def _split_agents(value: str) -> list[str]:
    cleaned = (value or "").strip().strip("'").strip()
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"[,;|/+]", cleaned) if part.strip()]


def _normalise_agent(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().strip("'").strip()).lower()


def _iter_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def read_drugs(in_tsv_paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Patient id -> recorded therapeutic agents, from the GDC clinical exports.

    Reads treatment and nothing else. It never looks at a sequencing record.
    """
    drugs_by_patient: dict[str, dict[str, Any]] = {}

    for tsv_path in in_tsv_paths:
        cohort = COHORT_BY_FILE.get(tsv_path.name, tsv_path.stem)

        for row in _iter_rows(tsv_path):
            patient_id = (row.get("cases.submitter_id") or "").strip()
            if not patient_id:
                continue

            agents = [
                agent
                for agent in _split_agents(row.get("treatments.therapeutic_agents") or "")
                if _normalise_agent(agent) not in EXCLUDED_AGENTS
            ]
            if not agents:
                continue

            entry = drugs_by_patient.setdefault(patient_id, {"cohort": cohort, "drugs": []})
            entry["drugs"].extend(agents)

    for entry in drugs_by_patient.values():
        seen: set[str] = set()
        unique: list[str] = []
        for drug in entry["drugs"]:
            key = _normalise_agent(drug)
            if key in seen:
                continue
            seen.add(key)
            unique.append(drug)
        entry["drugs"] = unique

    return drugs_by_patient


def read_biomarkers(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "patients" not in payload:
        raise SystemExit(f"{path} is not a biomarker payload (no 'patients' key)")
    return payload


def _gene_recurrence(cohort_patients: dict[str, list[dict]]) -> Counter:
    """How many patients in this cohort carry an alteration in each gene.

    Used only to choose which of a patient's alterations to name as the primary
    one for tools that take a single gene. Computed from the sequencing data
    alone: it cannot see any drug, and it cannot see this repo's evidence table,
    so it cannot preferentially surface variants the pipeline already answers.
    """
    counts: Counter = Counter()
    for alterations in cohort_patients.values():
        for gene in {alteration["gene"] for alteration in alterations}:
            counts[gene] += 1
    return counts


def _primary_alteration(alterations: list[dict], recurrence: Counter) -> dict:
    return sorted(
        alterations,
        key=lambda a: (
            -recurrence.get(a["gene"], 0),
            a["gene"],
            a["alteration_type"],
            a["protein_change"],
        ),
    )[0]


def build_labels(in_tsv_paths: list[Path], biomarkers_path: Path) -> dict[str, Any]:
    drugs_by_patient = read_drugs(in_tsv_paths)
    biomarker_payload = read_biomarkers(biomarkers_path)

    # Flatten the biomarker side to patient id, so the join key really is the
    # patient and nothing else.
    alterations_by_patient: dict[str, list[dict]] = {}
    biomarker_cohort_by_patient: dict[str, str] = {}
    sequenced_patients: set[str] = set()
    recurrence_by_cohort: dict[str, Counter] = {}

    for cohort, cohort_patients in biomarker_payload["patients"].items():
        recurrence_by_cohort[cohort] = _gene_recurrence(cohort_patients)
        for patient_id, alterations in cohort_patients.items():
            alterations_by_patient[patient_id] = alterations
            biomarker_cohort_by_patient[patient_id] = cohort

    for cohort_meta in biomarker_payload["studies"].values():
        sequenced_patients.update(cohort_meta.get("patient_ids_in_study") or [])

    labels: list[dict[str, Any]] = []
    counts_by_cohort: dict[str, int] = defaultdict(int)
    drug_only = 0
    drug_and_sequenced_no_alteration = 0

    for patient_id, drug_entry in sorted(drugs_by_patient.items()):
        alterations = alterations_by_patient.get(patient_id)
        if not alterations:
            if patient_id in sequenced_patients:
                drug_and_sequenced_no_alteration += 1
            else:
                drug_only += 1
            continue

        cohort = drug_entry["cohort"]
        recurrence = recurrence_by_cohort.get(biomarker_cohort_by_patient[patient_id], Counter())
        primary = _primary_alteration(alterations, recurrence)

        counts_by_cohort[cohort] += 1
        labels.append(
            {
                "patient_id": patient_id,
                "cohort": cohort,
                "biomarker_study": biomarker_cohort_by_patient[patient_id],
                "oncologist_recommended_drugs": drug_entry["drugs"],
                "gene": primary["gene"],
                "variant": primary["protein_change"],
                "alteration_type": primary["alteration_type"],
                "cancer_type_hint": CANCER_TYPE_BY_COHORT.get(cohort, cohort),
                "biomarkers": [
                    {
                        "gene": alteration["gene"],
                        "variant": alteration["protein_change"],
                        "alteration_type": alteration["alteration_type"],
                    }
                    for alteration in alterations
                ],
            }
        )

    return {
        "description": (
            "Oncologist concordance labels. Biomarker from the patient's cBioPortal sequencing "
            "record, drug from the patient's GDC clinical record, joined on patient id only. "
            "Neither field is derived from the other."
        ),
        "biomarker_source": biomarker_payload.get("source"),
        "gene_panel": biomarker_payload.get("gene_panel"),
        "drug_source_tsvs": [str(path) for path in in_tsv_paths],
        "primary_alteration_rule": (
            "Of the alterations the patient actually carries, the one in the gene altered in the "
            "most patients in that cohort. Computed from sequencing data alone; no drug and no "
            "evidence-table lookup takes part. The full list is kept in 'biomarkers'."
        ),
        "denominator": {
            "patients_with_a_recorded_drug": len(drugs_by_patient),
            "patients_with_a_panel_alteration": len(alterations_by_patient),
            "patients_with_both_scored": len(labels),
            "dropped_drug_but_not_sequenced": drug_only,
            "dropped_drug_and_sequenced_but_no_panel_alteration": drug_and_sequenced_no_alteration,
        },
        "counts_by_cohort": dict(sorted(counts_by_cohort.items())),
        "labels": labels,
        "n_labels": len(labels),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build oncologist concordance labels by joining GDC treatment records to cBioPortal sequencing records.",
    )
    parser.add_argument(
        "--in-tsv",
        nargs="*",
        default=DEFAULT_INPUT_FILES,
        help="Input clinical TSV paths (defaults to SKCM/LUAD/BRCA/COAD/GBM cohort files).",
    )
    parser.add_argument(
        "--biomarkers-json",
        default=DEFAULT_BIOMARKERS_JSON,
        help=(
            "Per-patient sequencing record produced by scripts/fetch_concordance_biomarkers.py "
            f"(default: {DEFAULT_BIOMARKERS_JSON})"
        ),
    )
    parser.add_argument(
        "--out-json",
        default="scripts/concordance_labels.json",
        help="Output labels JSON path (default: scripts/concordance_labels.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    in_tsvs = [(root / rel).resolve() for rel in args.in_tsv]
    biomarkers_json = (root / args.biomarkers_json).resolve()
    out_json = (root / args.out_json).resolve()

    missing = [str(path) for path in in_tsvs if not path.exists()]
    if missing:
        raise SystemExit(f"Input TSV(s) not found: {missing}")
    if not biomarkers_json.exists():
        raise SystemExit(
            f"Biomarker file not found: {biomarkers_json}\n"
            "Run: python scripts/fetch_concordance_biomarkers.py"
        )

    payload = build_labels(in_tsvs, biomarkers_json)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    denominator = payload["denominator"]
    print("Label denominator (a patient counts only with BOTH sources):")
    print(f"  patients with a recorded drug          : {denominator['patients_with_a_recorded_drug']}")
    print(f"  patients with a panel alteration       : {denominator['patients_with_a_panel_alteration']}")
    print(f"  dropped, drug but never sequenced      : {denominator['dropped_drug_but_not_sequenced']}")
    print(
        "  dropped, sequenced but nothing on panel: "
        f"{denominator['dropped_drug_and_sequenced_but_no_panel_alteration']}"
    )
    print(f"  SCORED (drug and biomarker)            : {denominator['patients_with_both_scored']}")
    print()
    print("Cases by cohort:")
    for cohort, count in payload["counts_by_cohort"].items():
        print(f"  {cohort}: {count}")
    print(f"Total cases: {payload['n_labels']}")
    print(f"Wrote labels to {out_json}")


if __name__ == "__main__":
    main()
