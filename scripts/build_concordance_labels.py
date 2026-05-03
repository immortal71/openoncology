from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
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

DRUG_BIOMARKER_MAP: dict[str, tuple[str, str, str]] = {
    "vemurafenib": ("BRAF", "V600E", "Melanoma"),
    "dabrafenib": ("BRAF", "V600E", "Melanoma"),
    "encorafenib": ("BRAF", "V600E", "Melanoma"),
    "trametinib": ("BRAF", "V600E", "Melanoma"),
    "binimetinib": ("BRAF", "V600E", "Melanoma"),
    "erlotinib": ("EGFR", "Activating", "NSCLC"),
    "gefitinib": ("EGFR", "Activating", "NSCLC"),
    "osimertinib": ("EGFR", "Activating", "NSCLC"),
    "afatinib": ("EGFR", "Activating", "NSCLC"),
    "sotorasib": ("KRAS", "G12C", "NSCLC"),
    "adagrasib": ("KRAS", "G12C", "NSCLC"),
    "olaparib": ("BRCA", "Pathogenic", "Breast/Ovarian"),
    "niraparib": ("BRCA", "Pathogenic", "Breast/Ovarian"),
    "talazoparib": ("BRCA", "Pathogenic", "Breast/Ovarian"),
    "ivosidenib": ("IDH1", "Mutant", "AML"),
    "enasidenib": ("IDH2", "Mutant", "AML"),
    "ipilimumab": ("TMB", "High", "Any"),
    "nivolumab": ("TMB", "High", "Any"),
    "pembrolizumab": ("TMB", "High", "Any"),
    "trastuzumab": ("ERBB2", "Amplified", "Breast"),
    "pertuzumab": ("ERBB2", "Amplified", "Breast"),
    "imatinib": ("KIT/BCR-ABL1", "Driver", "GIST/CML"),
    "everolimus": ("MTOR", "Pathway", "Any"),
    "temsirolimus": ("MTOR", "Pathway", "Any"),
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


def build_labels(in_tsv_paths: list[Path]) -> dict[str, Any]:
    patient_drugs: dict[tuple[str, str], list[str]] = defaultdict(list)
    patient_marker_profiles: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    counts_by_cohort: dict[str, int] = defaultdict(int)

    for tsv_path in in_tsv_paths:
        cohort = COHORT_BY_FILE.get(tsv_path.name, tsv_path.stem)
        rows = _iter_rows(tsv_path)

        for row in rows:
            patient_id = (row.get("cases.submitter_id") or "").strip()
            if not patient_id:
                continue

            raw_agents = row.get("treatments.therapeutic_agents") or ""
            agents = _split_agents(raw_agents)

            real_agents: list[str] = []
            for agent in agents:
                normalised = _normalise_agent(agent)
                if normalised in EXCLUDED_AGENTS:
                    continue
                real_agents.append(agent)

            if not real_agents:
                continue

            patient_key = (cohort, patient_id)
            patient_drugs[patient_key].extend(real_agents)

            for agent in real_agents:
                mapped = DRUG_BIOMARKER_MAP.get(_normalise_agent(agent))
                if mapped:
                    patient_marker_profiles[patient_key].add(mapped)

    labels: list[dict[str, Any]] = []

    for (cohort, patient_id), drugs in sorted(patient_drugs.items()):
        unique_drugs = []
        seen = set()
        for drug in drugs:
            key = _normalise_agent(drug)
            if key in seen:
                continue
            seen.add(key)
            unique_drugs.append(drug)

        marker_profiles = sorted(patient_marker_profiles.get((cohort, patient_id), set()))
        gene = marker_profiles[0][0] if marker_profiles else None
        variant = marker_profiles[0][1] if marker_profiles else None
        disease = marker_profiles[0][2] if marker_profiles else None

        counts_by_cohort[cohort] += 1

        labels.append(
            {
                "patient_id": patient_id,
                "cohort": cohort,
                "oncologist_recommended_drugs": unique_drugs,
                "gene": gene,
                "variant": variant,
                "cancer_type_hint": disease,
                "mapped_profiles": [
                    {"gene": g, "variant": v, "cancer": c} for g, v, c in marker_profiles
                ],
            }
        )

    return {
        "description": "Oncologist concordance labels built from multi-cohort clinical TSV therapeutic agents.",
        "source_tsvs": [str(path) for path in in_tsv_paths],
        "counts_by_cohort": dict(sorted(counts_by_cohort.items())),
        "labels": labels,
        "n_labels": len(labels),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build oncologist concordance labels from clinical TSV cohorts.")
    parser.add_argument(
        "--in-tsv",
        nargs="*",
        default=DEFAULT_INPUT_FILES,
        help="Input clinical TSV paths (defaults to SKCM/LUAD/BRCA/COAD/GBM cohort files).",
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
    out_json = (root / args.out_json).resolve()

    missing = [str(path) for path in in_tsvs if not path.exists()]
    if missing:
        raise SystemExit(f"Input TSV(s) not found: {missing}")

    payload = build_labels(in_tsvs)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Cases by cohort:")
    for cohort, count in payload["counts_by_cohort"].items():
        print(f"  {cohort}: {count}")
    print(f"Total cases: {payload['n_labels']}")
    print(f"Wrote labels to {out_json}")


if __name__ == "__main__":
    main()
