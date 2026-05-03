"""
Clinical Concordance Benchmark (Model vs Oncologist Recommendations)
===================================================================

Compares OpenOncology recommendations against clinician-provided drug choices
for the same patients.

Input options:
1) A benchmark JSON that already includes patient recommendations from this repo
   (e.g., real_patient_benchmark_100.json or real_patient_benchmark_200.json)
2) Optional external labels JSON containing oncologist-selected drugs keyed by
   patient_id/sample_id/patient_num.

This script computes:
- Top-1 concordance
- Top-3 concordance
- Mean Jaccard overlap between model top-3 and oncologist drugs
- Case-level comparison report

Usage:
    python scripts/benchmark_oncologist_concordance.py \
      --predictions-json real_patient_benchmark_100.json \
      --labels-json data/oncologist_labels_100.json \
      --out-json oncologist_concordance_100.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ONCOLOGIST_FIELDS = (
    "oncologist_recommended_drugs",
    "oncologist_drugs",
    "clinician_recommended_drugs",
    "tumor_board_recommended_drugs",
    "gold_drugs",
    "reference_drugs",
)


def _normalise_drug_name(name: str) -> str:
    value = (name or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _as_drug_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
        return raw
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
            elif isinstance(item, dict):
                for key in ("drug_name", "name", "compound_name", "label", "drug"):
                    candidate = item.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        out.append(candidate.strip())
                        break
        return out
    return []


def _extract_model_drugs(patient: dict[str, Any], include_custom: bool) -> list[str]:
    drugs: list[str] = []

    for field in ("top3_drugs", "approved_repurposing_drugs", "investigational_repurposing_drugs"):
        drugs.extend(_as_drug_list(patient.get(field)))

    if include_custom:
        brief = patient.get("custom_design_brief")
        if isinstance(brief, dict):
            for field in ("lead_candidates", "de_novo_candidates"):
                drugs.extend(_as_drug_list(brief.get(field)))

    return _unique_preserve_order(drugs)


def _extract_oncologist_drugs(patient: dict[str, Any]) -> list[str]:
    drugs: list[str] = []
    for field in DEFAULT_ONCOLOGIST_FIELDS:
        drugs.extend(_as_drug_list(patient.get(field)))
    return _unique_preserve_order(drugs)


def _patient_key(patient: dict[str, Any]) -> str:
    for field in ("patient_id", "sample_id", "case_id", "patient_num"):
        value = patient.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return f"{field}:{text}"
    return ""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_patients(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("patients")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _load_labels_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    rows = _load_patients(payload)
    if not rows and isinstance(payload, dict):
        alt_rows = payload.get("labels")
        if isinstance(alt_rows, list):
            rows = [row for row in alt_rows if isinstance(row, dict)]

    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _patient_key(row)
        if key:
            mapping[key] = row
    return mapping


def _format_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def run_concordance(
    predictions_json: Path,
    labels_json: Path | None,
    include_custom: bool,
) -> dict[str, Any]:
    prediction_payload = _load_json(predictions_json)
    patients = _load_patients(prediction_payload)
    labels_map = _load_labels_map(labels_json) if labels_json else {}

    compared = 0
    skipped_no_label = 0
    skipped_no_model = 0
    top1_hits = 0
    top3_hits = 0
    jaccard_sum = 0.0

    case_rows: list[dict[str, Any]] = []

    for patient in patients:
        row = dict(patient)
        key = _patient_key(row)
        if labels_map and key and key in labels_map:
            label_row = labels_map[key]
            row.update(label_row)

        oncologist_drugs = _extract_oncologist_drugs(row)
        if not oncologist_drugs:
            skipped_no_label += 1
            continue

        model_drugs = _extract_model_drugs(row, include_custom=include_custom)
        if not model_drugs:
            skipped_no_model += 1
            continue

        compared += 1

        model_top3 = model_drugs[:3]
        model_top1 = model_top3[0] if model_top3 else ""

        model_norm_top3 = [_normalise_drug_name(drug) for drug in model_top3 if drug]
        onc_norm = {_normalise_drug_name(drug) for drug in oncologist_drugs if drug}

        top1_match = bool(model_top1) and (_normalise_drug_name(model_top1) in onc_norm)
        top3_overlap = [drug for drug in model_top3 if _normalise_drug_name(drug) in onc_norm]
        top3_match = len(top3_overlap) > 0

        if top1_match:
            top1_hits += 1
        if top3_match:
            top3_hits += 1

        model_set = set(model_norm_top3)
        onc_set = set(onc_norm)
        union = model_set | onc_set
        inter = model_set & onc_set
        jaccard = (len(inter) / len(union)) if union else 0.0
        jaccard_sum += jaccard

        case_rows.append(
            {
                "patient_id": row.get("patient_id"),
                "sample_id": row.get("sample_id"),
                "patient_num": row.get("patient_num"),
                "cancer_type": row.get("cancer_type"),
                "gene": row.get("gene"),
                "protein_change": row.get("protein_change"),
                "model_top1": model_top1,
                "model_top3": model_top3,
                "oncologist_drugs": oncologist_drugs,
                "top1_match": top1_match,
                "top3_match": top3_match,
                "top3_overlap_drugs": top3_overlap,
                "jaccard_top3": round(jaccard, 4),
            }
        )

    mean_jaccard = round((jaccard_sum / compared), 4) if compared else 0.0

    return {
        "description": "Clinical concordance benchmark between OpenOncology outputs and oncologist-selected therapies.",
        "predictions_json": str(predictions_json),
        "labels_json": str(labels_json) if labels_json else None,
        "include_custom": include_custom,
        "total_patients_in_predictions": len(patients),
        "patients_compared": compared,
        "skipped_no_oncologist_label": skipped_no_label,
        "skipped_no_model_recommendation": skipped_no_model,
        "metrics": {
            "top1_concordance_count": top1_hits,
            "top1_concordance_pct": _format_pct(top1_hits, compared),
            "top3_concordance_count": top3_hits,
            "top3_concordance_pct": _format_pct(top3_hits, compared),
            "mean_jaccard_top3": mean_jaccard,
        },
        "cases": case_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare OpenOncology recommendations with oncologist-selected drugs.",
    )
    parser.add_argument(
        "--predictions-json",
        default="real_patient_benchmark_100.json",
        help="Benchmark JSON containing model outputs (default: real_patient_benchmark_100.json).",
    )
    parser.add_argument(
        "--labels-json",
        default=None,
        help=(
            "Optional labels JSON containing oncologist-selected drugs keyed by patient_id/sample_id/patient_num. "
            "If omitted, labels are read from fields already present in predictions JSON."
        ),
    )
    parser.add_argument(
        "--include-custom",
        action="store_true",
        help="Include custom-design lead candidates when comparing model vs oncologist recommendations.",
    )
    parser.add_argument(
        "--out-json",
        default="oncologist_concordance_results.json",
        help="Output JSON file path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = Path(__file__).resolve().parents[1]
    predictions_json = (root / args.predictions_json).resolve()
    if not predictions_json.exists():
        raise SystemExit(f"Predictions file not found: {predictions_json}")

    labels_json: Path | None = None
    if args.labels_json:
        labels_json = (root / args.labels_json).resolve()
        if not labels_json.exists():
            raise SystemExit(f"Labels file not found: {labels_json}")

    report = run_concordance(
        predictions_json=predictions_json,
        labels_json=labels_json,
        include_custom=bool(args.include_custom),
    )

    out_json = (root / args.out_json).resolve()
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    metrics = report["metrics"]
    print("=" * 72)
    print("ONCOLOGIST CONCORDANCE BENCHMARK")
    print("=" * 72)
    print(f"Patients in predictions: {report['total_patients_in_predictions']}")
    print(f"Patients compared:       {report['patients_compared']}")
    print(f"Skipped (no labels):     {report['skipped_no_oncologist_label']}")
    print(f"Skipped (no model rec):  {report['skipped_no_model_recommendation']}")
    print("-")
    print(f"Top-1 concordance:       {metrics['top1_concordance_count']} ({metrics['top1_concordance_pct']}%)")
    print(f"Top-3 concordance:       {metrics['top3_concordance_count']} ({metrics['top3_concordance_pct']}%)")
    print(f"Mean Jaccard@3:          {metrics['mean_jaccard_top3']}")
    print(f"Report written:          {out_json}")
    print("=" * 72)


if __name__ == "__main__":
    main()
