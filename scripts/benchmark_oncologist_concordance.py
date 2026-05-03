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
import os
import re
import sys
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


BRAF_V600E_EQUIVALENTS = [
    "vemurafenib",
    "dabrafenib",
    "encorafenib",
    "trametinib",
    "binimetinib",
    "cobimetinib",
]

DRUG_EQUIVALENCE_GROUPS: dict[str, list[str]] = {
    "braf_inhibitors": ["vemurafenib", "dabrafenib", "encorafenib"],
    "mek_inhibitors": ["trametinib", "binimetinib", "cobimetinib"],
    "checkpoint_inhibitors": ["ipilimumab", "nivolumab", "pembrolizumab"],
    "egfr_tkis": ["erlotinib", "gefitinib", "osimertinib", "afatinib"],
    "kras_g12c": ["sotorasib", "adagrasib"],
}


def _normalise_drug_name(name: str) -> str:
    value = (name or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def _build_equivalence_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for group_name, drugs in DRUG_EQUIVALENCE_GROUPS.items():
        for drug in drugs:
            lookup[_normalise_drug_name(drug)] = group_name
    return lookup


DRUG_EQUIVALENCE_LOOKUP = _build_equivalence_lookup()


def _canonical_drug_token(name: str) -> str:
    norm = _normalise_drug_name(name)
    if not norm:
        return ""
    group = DRUG_EQUIVALENCE_LOOKUP.get(norm)
    if group:
        return f"group:{group}"
    return f"drug:{norm}"


def _drug_token_set(drugs: list[str]) -> set[str]:
    return {token for token in (_canonical_drug_token(drug) for drug in drugs if drug) if token}


def _equivalent_overlap(model_top3: list[str], oncologist_drugs: list[str]) -> list[str]:
    onc_tokens = _drug_token_set(oncologist_drugs)
    return [drug for drug in model_top3 if _canonical_drug_token(drug) in onc_tokens]


def _exact_overlap(model_top3: list[str], oncologist_drugs: list[str]) -> list[str]:
    onc_exact = {_normalise_drug_name(drug) for drug in oncologist_drugs if drug}
    return [drug for drug in model_top3 if _normalise_drug_name(drug) in onc_exact]


def _score_case(model_top3: list[str], oncologist_drugs: list[str]) -> dict[str, Any]:
    model_top1 = model_top3[0] if model_top3 else ""

    onc_exact = {_normalise_drug_name(drug) for drug in oncologist_drugs if drug}
    model_exact = {_normalise_drug_name(drug) for drug in model_top3 if drug}
    exact_overlap = _exact_overlap(model_top3, oncologist_drugs)
    exact_top1 = bool(model_top1) and (_normalise_drug_name(model_top1) in onc_exact)
    exact_top3 = len(exact_overlap) > 0
    exact_union = model_exact | onc_exact
    exact_inter = model_exact & onc_exact
    exact_jaccard = (len(exact_inter) / len(exact_union)) if exact_union else 0.0

    onc_equiv = _drug_token_set(oncologist_drugs)
    model_equiv = _drug_token_set(model_top3)
    equiv_overlap = _equivalent_overlap(model_top3, oncologist_drugs)
    equiv_top1 = bool(model_top1) and (_canonical_drug_token(model_top1) in onc_equiv)
    equiv_top3 = len(equiv_overlap) > 0
    equiv_union = model_equiv | onc_equiv
    equiv_inter = model_equiv & onc_equiv
    equiv_jaccard = (len(equiv_inter) / len(equiv_union)) if equiv_union else 0.0

    return {
        "model_top1": model_top1,
        "exact": {
            "top1": exact_top1,
            "top3": exact_top3,
            "overlap": exact_overlap,
            "jaccard": exact_jaccard,
        },
        "equivalence": {
            "top1": equiv_top1,
            "top3": equiv_top3,
            "overlap": equiv_overlap,
            "jaccard": equiv_jaccard,
        },
    }


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


def _norm_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _partial_text_match(a: Any, b: Any) -> bool:
    left = _norm_text(a)
    right = _norm_text(b)
    if not left or not right:
        return False
    return (left in right) or (right in left)


def _extract_variant(row: dict[str, Any]) -> str:
    for field in ("variant", "protein_change", "alteration", "mutation", "change"):
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_cancer_hint(row: dict[str, Any]) -> str:
    for field in ("cancer_type_hint", "cancer_type", "cohort"):
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return "Any"


def _setup_api_path() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_dir = os.path.join(project_root, "api")
    for p in (project_root, api_dir):
        if p not in sys.path:
            sys.path.insert(0, p)


def _drug_names_from_candidates(candidates: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for candidate in candidates:
        name = candidate.get("drug_name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return _unique_preserve_order(names)


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
    label_rows: list[dict[str, Any]] = []
    if labels_json:
        labels_payload = _load_json(labels_json)
        label_rows = _load_patients(labels_payload)
        if not label_rows and isinstance(labels_payload, dict):
            alt_rows = labels_payload.get("labels")
            if isinstance(alt_rows, list):
                label_rows = [row for row in alt_rows if isinstance(row, dict)]
    labels_map = _load_labels_map(labels_json) if labels_json else {}

    # When external labels are provided, run direct pipeline prediction on each unique gene+variant.
    if labels_json:
        _setup_api_path()
        from scripts.fetch_real_patients import tier1_fda_evidence, tier2_repurposing

        processed = 0
        skipped_no_label = 0
        tier1_cases = 0
        tier2_cases = 0
        no_prediction_cases = 0
        exact_top1_hits = 0
        exact_top3_hits = 0
        exact_jaccard_sum = 0.0
        equiv_top1_hits = 0
        equiv_top3_hits = 0
        equiv_jaccard_sum = 0.0

        case_rows: list[dict[str, Any]] = []

        combo_cache: dict[tuple[str, str], dict[str, Any]] = {}

        labels_with_gene_variant = 0

        for label in label_rows:
            oncologist_drugs = _extract_oncologist_drugs(label)
            if not oncologist_drugs:
                skipped_no_label += 1
                continue

            processed += 1
            label_gene = _norm_text(label.get("gene"))
            label_variant = _norm_text(_extract_variant(label))

            if not label_gene or not label_variant:
                no_prediction_cases += 1
                case_rows.append(
                    {
                        "label_patient_id": label.get("patient_id"),
                        "cohort": label.get("cohort"),
                        "label_gene": label.get("gene"),
                        "label_variant": _extract_variant(label),
                        "cancer_type_hint": _extract_cancer_hint(label),
                        "oncologist_drugs": oncologist_drugs,
                        "prediction_tier": "NONE",
                        "prediction_reason": "missing_gene_or_variant",
                        "model_top1": "",
                        "model_top3": [],
                        "top1_match": False,
                        "top3_match": False,
                        "top3_overlap_drugs": [],
                        "jaccard_top3": 0.0,
                        "exact_top1_match": False,
                        "exact_top3_match": False,
                        "exact_overlap_drugs": [],
                        "exact_jaccard_top3": 0.0,
                        "equiv_top1_match": False,
                        "equiv_top3_match": False,
                        "equiv_overlap_drugs": [],
                        "equiv_jaccard_top3": 0.0,
                    }
                )
                continue

            labels_with_gene_variant += 1
            combo_key = (label_gene, label_variant)

            if combo_key not in combo_cache:
                gene_raw = str(label.get("gene") or "").strip()
                variant_raw = str(_extract_variant(label) or "").strip()
                cancer_hint = _extract_cancer_hint(label)

                tier1_ranked = tier1_fda_evidence(gene_raw, variant_raw)
                tier1_drugs = _drug_names_from_candidates(tier1_ranked)[:3]

                tier2 = tier2_repurposing(gene_raw, variant_raw, cancer_hint)
                tier2_approved = _drug_names_from_candidates(tier2.get("approved") or [])
                tier2_investigational = _drug_names_from_candidates(tier2.get("investigational") or [])

                if tier1_drugs:
                    selected_tier = "TIER1"
                    selected_top3 = tier1_drugs[:3]
                elif tier2_approved:
                    selected_tier = "TIER2"
                    selected_top3 = tier2_approved[:3]
                elif tier2_investigational:
                    selected_tier = "TIER2"
                    selected_top3 = tier2_investigational[:3]
                else:
                    selected_tier = "NONE"
                    selected_top3 = []

                combo_cache[combo_key] = {
                    "gene": gene_raw,
                    "variant": variant_raw,
                    "cancer_hint": cancer_hint,
                    "tier1_drugs": tier1_drugs,
                    "tier2_approved_drugs": tier2_approved,
                    "tier2_investigational_drugs": tier2_investigational,
                    "selected_tier": selected_tier,
                    "selected_top3": selected_top3,
                }

            pred = combo_cache[combo_key]
            model_top3 = list(pred["selected_top3"])

            if pred["selected_tier"] == "TIER1":
                tier1_cases += 1
            elif pred["selected_tier"] == "TIER2":
                tier2_cases += 1
            else:
                no_prediction_cases += 1

            if not model_top3:
                case_rows.append(
                    {
                        "label_patient_id": label.get("patient_id"),
                        "cohort": label.get("cohort"),
                        "label_gene": label.get("gene"),
                        "label_variant": _extract_variant(label),
                        "cancer_type_hint": _extract_cancer_hint(label),
                        "oncologist_drugs": oncologist_drugs,
                        "prediction_tier": "NONE",
                        "model_top1": "",
                        "model_top3": [],
                        "top1_match": False,
                        "top3_match": False,
                        "top3_overlap_drugs": [],
                        "jaccard_top3": 0.0,
                        "exact_top1_match": False,
                        "exact_top3_match": False,
                        "exact_overlap_drugs": [],
                        "exact_jaccard_top3": 0.0,
                        "equiv_top1_match": False,
                        "equiv_top3_match": False,
                        "equiv_overlap_drugs": [],
                        "equiv_jaccard_top3": 0.0,
                    }
                )
                continue

            score = _score_case(model_top3, oncologist_drugs)
            model_top1 = score["model_top1"]

            exact_top1 = bool(score["exact"]["top1"])
            exact_top3 = bool(score["exact"]["top3"])
            exact_overlap = list(score["exact"]["overlap"])
            exact_jaccard = float(score["exact"]["jaccard"])

            equiv_top1 = bool(score["equivalence"]["top1"])
            equiv_top3 = bool(score["equivalence"]["top3"])
            equiv_overlap = list(score["equivalence"]["overlap"])
            equiv_jaccard = float(score["equivalence"]["jaccard"])

            if exact_top1:
                exact_top1_hits += 1
            if exact_top3:
                exact_top3_hits += 1
            exact_jaccard_sum += exact_jaccard

            if equiv_top1:
                equiv_top1_hits += 1
            if equiv_top3:
                equiv_top3_hits += 1
            equiv_jaccard_sum += equiv_jaccard

            case_rows.append(
                {
                    "label_patient_id": label.get("patient_id"),
                    "cohort": label.get("cohort"),
                    "label_gene": label.get("gene"),
                    "label_variant": _extract_variant(label),
                    "cancer_type_hint": _extract_cancer_hint(label),
                    "prediction_tier": pred["selected_tier"],
                    "tier1_drugs": pred["tier1_drugs"],
                    "tier2_approved_drugs": pred["tier2_approved_drugs"],
                    "tier2_investigational_drugs": pred["tier2_investigational_drugs"],
                    "model_top1": model_top1,
                    "model_top3": model_top3,
                    "oncologist_drugs": oncologist_drugs,
                    "top1_match": equiv_top1,
                    "top3_match": equiv_top3,
                    "top3_overlap_drugs": equiv_overlap,
                    "jaccard_top3": round(equiv_jaccard, 4),
                    "exact_top1_match": exact_top1,
                    "exact_top3_match": exact_top3,
                    "exact_overlap_drugs": exact_overlap,
                    "exact_jaccard_top3": round(exact_jaccard, 4),
                    "equiv_top1_match": equiv_top1,
                    "equiv_top3_match": equiv_top3,
                    "equiv_overlap_drugs": equiv_overlap,
                    "equiv_jaccard_top3": round(equiv_jaccard, 4),
                }
            )

        scored_cases = processed - no_prediction_cases
        exact_mean_jaccard = round((exact_jaccard_sum / scored_cases), 4) if scored_cases else 0.0
        equiv_mean_jaccard = round((equiv_jaccard_sum / scored_cases), 4) if scored_cases else 0.0

        prediction_pct = _format_pct(scored_cases, processed)
        no_prediction_pct = _format_pct(no_prediction_cases, processed)

        metrics_exact = {
            "top1_concordance_count": exact_top1_hits,
            "top1_concordance_pct": _format_pct(exact_top1_hits, scored_cases),
            "top3_concordance_count": exact_top3_hits,
            "top3_concordance_pct": _format_pct(exact_top3_hits, scored_cases),
            "mean_jaccard_top3": exact_mean_jaccard,
        }
        metrics_equiv = {
            "top1_concordance_count": equiv_top1_hits,
            "top1_concordance_pct": _format_pct(equiv_top1_hits, scored_cases),
            "top3_concordance_count": equiv_top3_hits,
            "top3_concordance_pct": _format_pct(equiv_top3_hits, scored_cases),
            "mean_jaccard_top3": equiv_mean_jaccard,
        }

        return {
            "description": "Clinical concordance benchmark by running OpenOncology tiered matching directly on label biomarker cases.",
            "predictions_json": None,
            "labels_json": str(labels_json),
            "matching_mode": "direct_pipeline_per_label_gene_variant",
            "vintage_adjustment_note": (
                "Concordance uses drug equivalence groups so clinically interchangeable agents "
                "across treatment vintages are counted as hits (e.g., BRAF/MEK class substitutions)."
            ),
            "drug_equivalence_groups": DRUG_EQUIVALENCE_GROUPS,
            "include_custom": include_custom,
            "total_labels": len(label_rows),
            "labels_with_gene_variant": labels_with_gene_variant,
            "total_label_cases_processed": processed,
            "tier_coverage": {
                "tier1_prediction_cases": tier1_cases,
                "tier2_prediction_cases": tier2_cases,
                "no_prediction_cases": no_prediction_cases,
            },
            "coverage_stats": {
                "total_label_cases": processed,
                "cases_with_pipeline_prediction": scored_cases,
                "cases_with_pipeline_prediction_pct": prediction_pct,
                "cases_with_no_prediction": no_prediction_cases,
                "cases_with_no_prediction_pct": no_prediction_pct,
                "note": (
                    "high no-prediction rate reflects that most TCGA patients have non-actionable mutations "
                    "or received chemotherapy rather than targeted therapy"
                ),
            },
            "skipped_no_oncologist_label": skipped_no_label,
            "unique_gene_variant_combinations": len(combo_cache),
            "cases_with_predictions": scored_cases,
            "metrics": metrics_equiv,
            "metrics_exact": metrics_exact,
            "metrics_equivalence_adjusted": metrics_equiv,
            "cases": case_rows,
        }

    compared = 0
    skipped_no_label = 0
    skipped_no_model = 0
    exact_top1_hits = 0
    exact_top3_hits = 0
    exact_jaccard_sum = 0.0
    equiv_top1_hits = 0
    equiv_top3_hits = 0
    equiv_jaccard_sum = 0.0

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

        score = _score_case(model_top3, oncologist_drugs)

        exact_top1 = bool(score["exact"]["top1"])
        exact_top3 = bool(score["exact"]["top3"])
        exact_overlap = list(score["exact"]["overlap"])
        exact_jaccard = float(score["exact"]["jaccard"])

        equiv_top1 = bool(score["equivalence"]["top1"])
        equiv_top3 = bool(score["equivalence"]["top3"])
        equiv_overlap = list(score["equivalence"]["overlap"])
        equiv_jaccard = float(score["equivalence"]["jaccard"])

        if exact_top1:
            exact_top1_hits += 1
        if exact_top3:
            exact_top3_hits += 1
        exact_jaccard_sum += exact_jaccard

        if equiv_top1:
            equiv_top1_hits += 1
        if equiv_top3:
            equiv_top3_hits += 1
        equiv_jaccard_sum += equiv_jaccard

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
                "top1_match": equiv_top1,
                "top3_match": equiv_top3,
                "top3_overlap_drugs": equiv_overlap,
                "jaccard_top3": round(equiv_jaccard, 4),
                "exact_top1_match": exact_top1,
                "exact_top3_match": exact_top3,
                "exact_overlap_drugs": exact_overlap,
                "exact_jaccard_top3": round(exact_jaccard, 4),
                "equiv_top1_match": equiv_top1,
                "equiv_top3_match": equiv_top3,
                "equiv_overlap_drugs": equiv_overlap,
                "equiv_jaccard_top3": round(equiv_jaccard, 4),
            }
        )

    exact_mean_jaccard = round((exact_jaccard_sum / compared), 4) if compared else 0.0
    equiv_mean_jaccard = round((equiv_jaccard_sum / compared), 4) if compared else 0.0

    metrics_exact = {
        "top1_concordance_count": exact_top1_hits,
        "top1_concordance_pct": _format_pct(exact_top1_hits, compared),
        "top3_concordance_count": exact_top3_hits,
        "top3_concordance_pct": _format_pct(exact_top3_hits, compared),
        "mean_jaccard_top3": exact_mean_jaccard,
    }
    metrics_equiv = {
        "top1_concordance_count": equiv_top1_hits,
        "top1_concordance_pct": _format_pct(equiv_top1_hits, compared),
        "top3_concordance_count": equiv_top3_hits,
        "top3_concordance_pct": _format_pct(equiv_top3_hits, compared),
        "mean_jaccard_top3": equiv_mean_jaccard,
    }

    return {
        "description": "Clinical concordance benchmark between OpenOncology outputs and oncologist-selected therapies.",
        "predictions_json": str(predictions_json),
        "labels_json": str(labels_json) if labels_json else None,
        "vintage_adjustment_note": (
            "Concordance uses drug equivalence groups so clinically interchangeable agents "
            "across treatment vintages are counted as hits (e.g., BRAF/MEK class substitutions)."
        ),
        "drug_equivalence_groups": DRUG_EQUIVALENCE_GROUPS,
        "include_custom": include_custom,
        "total_patients_in_predictions": len(patients),
        "patients_compared": compared,
        "skipped_no_oncologist_label": skipped_no_label,
        "skipped_no_model_recommendation": skipped_no_model,
        "metrics": metrics_equiv,
        "metrics_exact": metrics_exact,
        "metrics_equivalence_adjusted": metrics_equiv,
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

    metrics_exact = report.get("metrics_exact") or report["metrics"]
    metrics_equiv = report.get("metrics_equivalence_adjusted") or report["metrics"]
    print("=" * 72)
    print("ONCOLOGIST CONCORDANCE BENCHMARK")
    print("=" * 72)
    if report.get("matching_mode") == "direct_pipeline_per_label_gene_variant":
        coverage = report.get("coverage_stats") or {}
        tier_cov = report.get("tier_coverage") or {}
        print(f"Total label cases:       {coverage.get('total_label_cases', report.get('total_label_cases_processed', 0))}")
        print(f"Tier 1 prediction cases: {tier_cov.get('tier1_prediction_cases', 0)}")
        print(f"Tier 2 prediction cases: {tier_cov.get('tier2_prediction_cases', 0)}")
        print(
            "Cases with prediction:    "
            f"{coverage.get('cases_with_pipeline_prediction', report.get('cases_with_predictions', 0))} "
            f"({coverage.get('cases_with_pipeline_prediction_pct', 0.0)}%)"
        )
        print(
            "Cases with no prediction: "
            f"{coverage.get('cases_with_no_prediction', tier_cov.get('no_prediction_cases', 0))} "
            f"({coverage.get('cases_with_no_prediction_pct', 0.0)}%)"
        )
        if coverage.get("note"):
            print(f"Coverage note:           {coverage['note']}")
        print(f"Skipped (no labels):     {report.get('skipped_no_oncologist_label', 0)}")
    else:
        print(f"Patients in predictions: {report['total_patients_in_predictions']}")
        print(f"Patients compared:       {report['patients_compared']}")
        print(f"Skipped (no labels):     {report['skipped_no_oncologist_label']}")
        print(f"Skipped (no model rec):  {report['skipped_no_model_recommendation']}")
    print("-")
    print("Exact Match Results (strict):")
    print(f"Top-1:                   {metrics_exact['top1_concordance_pct']}% ({metrics_exact['top1_concordance_count']}/{report.get('cases_with_predictions', report.get('patients_compared', 0))})")
    print(f"Top-3:                   {metrics_exact['top3_concordance_pct']}% ({metrics_exact['top3_concordance_count']}/{report.get('cases_with_predictions', report.get('patients_compared', 0))})")
    print(f"Jaccard:                 {metrics_exact['mean_jaccard_top3']}")
    print("-")
    print("Equivalence-Adjusted Results (clinical class match):")
    print(f"Top-1:                   {metrics_equiv['top1_concordance_pct']}% ({metrics_equiv['top1_concordance_count']}/{report.get('cases_with_predictions', report.get('patients_compared', 0))})")
    print(f"Top-3:                   {metrics_equiv['top3_concordance_pct']}% ({metrics_equiv['top3_concordance_count']}/{report.get('cases_with_predictions', report.get('patients_compared', 0))})")
    print(f"Jaccard:                 {metrics_equiv['mean_jaccard_top3']}")
    if report.get("vintage_adjustment_note"):
        print("-")
        print(f"Note: {report['vintage_adjustment_note']}")
    print(f"Report written:          {out_json}")
    print("=" * 72)


if __name__ == "__main__":
    main()
