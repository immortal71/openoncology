#!/usr/bin/env python3
"""Industry-Grade Validation with Holdout P@3 Stability Testing

Extends the base industry_grade_validation.py to:
1. Split cases into train (marked with is_holdout=False) and holdout (is_holdout=True)
2. Compute metrics separately for each set
3. Validate that P@3 remains stable (holdout_p3 ≥ 0.95 * train_p3)
4. Flag overfitting if holdout performance collapses

Key principle: P@3 should NOT improve just because n increases. If it does, the
benchmark is contaminated (train/test leakage) or the model is overfitting.

Usage:
    python scripts/validate_p3_stability.py
    python scripts/validate_p3_stability.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from api.ai.ranking import rank_candidates
from api.services.benchmark import (
    ADDITIONAL_VALIDATION_CASES,
    TRIAL_DERIVED_CASES,
    HARD_CLINICAL_CASES,
    hit_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    standard_precision_at_k,
)
from api.services.oncokb_evidence import get_all_drugs_for_variant_live
from scripts.holdout_validation import (
    split_train_holdout,
    compute_p3_stability,
)


def _norm_drug(name: str) -> str:
    return re.sub(r"[\s\-.]", "", str(name).lower())


def _is_match(name: str, known_drugs: list[str]) -> bool:
    n = name.lower().replace(" ", "")
    return any(k.lower().replace(" ", "") in n or n in k.lower().replace(" ", "") for k in known_drugs)


def _case_key(case: dict[str, Any]) -> tuple[str, str, str, bool]:
    return (
        str(case.get("gene", "")),
        str(case.get("variant", "")),
        str(case.get("cancer_type", "")),
        bool(case.get("expect_empty", False)),
    )


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _mean_ci_normal_approx(values: list[float], z: float = 1.96) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        return (mean, mean)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    se = math.sqrt(var / n)
    lo = max(0.0, mean - z * se)
    hi = min(1.0, mean + z * se)
    return (lo, hi)


def _co_mutated_genes(case: dict[str, Any]) -> list[str]:
    raw = case.get("co_mutated_genes") or case.get("comutations") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    primary = str(case.get("gene", "")).upper()
    for item in raw:
        token = str(item).strip().upper()
        if not token or any(ch.isdigit() for ch in token):
            continue
        if token == primary:
            continue
        if re.fullmatch(r"[A-Z0-9]{2,12}", token):
            out.append(token)
    return sorted(set(out))


def _build_candidates(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Build and rank candidates for a case."""
    gene = case["gene"]
    variant = case["variant"]
    cancer_type = case.get("cancer_type")
    level_map = get_all_drugs_for_variant_live(gene, variant, cancer_type)
    co_mutated_genes = _co_mutated_genes(case)

    candidates: list[dict[str, Any]] = []
    for drug_name, level in level_map.items():
        level_upper = str(level).upper().strip()
        if not level_upper:
            continue
        candidates.append(
            {
                "drug_name": str(drug_name).title(),
                "oncokb_level": level_upper,
                "is_approved": level_upper == "LEVEL_1",
                "max_phase": 4 if level_upper == "LEVEL_1" else (3 if level_upper == "LEVEL_2" else 2),
                "target_gene": gene,
                "co_mutated_genes": co_mutated_genes,
            }
        )
    return rank_candidates(candidates)


def _get_all_external_cases() -> list[dict[str, Any]]:
    """Get all external validation cases (including trial-derived)."""
    dev_keys = {_case_key(c) for c in HARD_CLINICAL_CASES}
    
    # Combine all external pools
    all_external = list(ADDITIONAL_VALIDATION_CASES) + list(TRIAL_DERIVED_CASES)
    
    # Filter out any overlap with development set
    full_external = [c for c in all_external if _case_key(c) not in dev_keys]
    
    # Sort for deterministic order
    return sorted(full_external, key=lambda c: str(c.get("case_id", "")))


def compute_metrics_for_cases(
    cases: list[dict[str, Any]],
    verbose: bool = False,
) -> dict[str, Any]:
    """Compute metrics for a set of cases.
    
    Returns dict with keys: p3, hit_at_3, false_positive_rate, n_sensitivity, n_specificity
    """
    std_p3_vals: list[float] = []
    hit3_vals: list[float] = []
    mrr_vals: list[float] = []
    ndcg3_vals: list[float] = []
    fp_count = 0
    sensitivity_case_count = 0
    specificity_case_count = 0

    for case in cases:
        expect_empty = bool(case.get("expect_empty", False))
        ranked = _build_candidates(case)
        ranked_names = [r.get("drug_name", "") for r in ranked if r.get("drug_name")]

        if expect_empty:
            specificity_case_count += 1
            top3 = ranked[:3]
            high_conf = [r for r in top3 if r.get("rank_score", 0) > 0.25 and r.get("oncokb_level")]
            if high_conf:
                fp_count += 1
            continue

        known = case.get("known_drugs", []) or []
        sensitivity_case_count += 1

        std_p3 = standard_precision_at_k(ranked_names, known, 3)
        h3 = 1.0 if hit_at_k(ranked_names, known, 3) else 0.0
        mrr = mean_reciprocal_rank(ranked_names, known)
        ndcg3 = ndcg_at_k(ranked_names, known, 3)

        std_p3_vals.append(std_p3)
        hit3_vals.append(h3)
        mrr_vals.append(mrr)
        ndcg3_vals.append(ndcg3)

    fp_rate = (fp_count / specificity_case_count) if specificity_case_count else 0.0
    hit3_success = sum(1 for v in hit3_vals if v >= 1.0)
    hit3_ci = (
        (hit3_success / len(hit3_vals), hit3_success / len(hit3_vals))
        if hit3_vals
        else (0.0, 0.0)
    )

    return {
        "p3": _avg(std_p3_vals),
        "p3_ci95": _mean_ci_normal_approx(std_p3_vals),
        "hit_at_3": _avg(hit3_vals),
        "hit_at_3_ci95": hit3_ci,
        "mrr": _avg(mrr_vals),
        "ndcg3": _avg(ndcg3_vals),
        "false_positive_rate": fp_rate,
        "n_sensitivity": sensitivity_case_count,
        "n_specificity": specificity_case_count,
    }


def validate_p3_stability_comprehensive() -> dict[str, Any]:
    """Run comprehensive P@3 stability validation on train vs holdout split."""
    
    logger.info("=" * 80)
    logger.info("P@3 STABILITY VALIDATION (Train vs Holdout)")
    logger.info("=" * 80)
    
    # Get all external cases
    all_external = _get_all_external_cases()
    logger.info(f"Total external cases: {len(all_external)}")
    
    # Split into train and holdout
    train_cases, holdout_cases = split_train_holdout(
        all_external,
        holdout_frac=0.30,
        preserve_difficulty_distribution=True,
    )
    
    logger.info(f"Train set: {len(train_cases)} cases")
    logger.info(f"Holdout set: {len(holdout_cases)} cases")
    
    # Compute metrics for both
    logger.info("\nComputing metrics for train set...")
    train_metrics = compute_metrics_for_cases(train_cases, verbose=True)
    
    logger.info("Computing metrics for holdout set...")
    holdout_metrics = compute_metrics_for_cases(holdout_cases, verbose=True)
    
    # Compute stability
    stability = compute_p3_stability(train_metrics, holdout_metrics)
    
    # Build report
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "profile": "p3_stability_v1",
        "train_set": {
            "n_cases": len(train_cases),
            "n_sensitivity": train_metrics["n_sensitivity"],
            "n_specificity": train_metrics["n_specificity"],
            "standard_precision_at_3": round(train_metrics["p3"], 4),
            "standard_precision_at_3_ci95": [
                round(train_metrics["p3_ci95"][0], 4),
                round(train_metrics["p3_ci95"][1], 4),
            ],
            "hit_at_3": round(train_metrics["hit_at_3"], 4),
            "false_positive_rate": round(train_metrics["false_positive_rate"], 4),
        },
        "holdout_set": {
            "n_cases": len(holdout_cases),
            "n_sensitivity": holdout_metrics["n_sensitivity"],
            "n_specificity": holdout_metrics["n_specificity"],
            "standard_precision_at_3": round(holdout_metrics["p3"], 4),
            "standard_precision_at_3_ci95": [
                round(holdout_metrics["p3_ci95"][0], 4),
                round(holdout_metrics["p3_ci95"][1], 4),
            ],
            "hit_at_3": round(holdout_metrics["hit_at_3"], 4),
            "false_positive_rate": round(holdout_metrics["false_positive_rate"], 4),
        },
        "stability": {
            "p3_degradation_percent": round(stability.p3_degradation, 2),
            "hit_at_3_degradation_percent": round(stability.hit_at_3_degradation, 2),
            "fpr_increase_pp": round(stability.fpr_increase, 2),
            "is_overfitting": stability.is_overfitting,
            "is_stable": stability.is_stable,
        },
        "interpretation": stability.summary(),
        "gates": {
            "p3_stability_pass": stability.p3_degradation < 5.0,  # < 5% degradation
            "hit_at_3_stability_pass": stability.hit_at_3_degradation < 5.0,
            "fpr_stability_pass": stability.fpr_increase < 2.0,  # < 2pp increase
            "no_overfitting": not stability.is_overfitting,
            "overall_stability": stability.is_stable,
        },
    }
    
    return report


def main() -> int:
    """Run P@3 stability validation and save report."""
    parser = argparse.ArgumentParser(description="Validate P@3 stability on train vs holdout sets")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    report = validate_p3_stability_comprehensive()
    
    out_path = os.path.join(ROOT, "p3_stability_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\nReport saved to {out_path}")
    logger.info("\n" + "=" * 80)
    print(report["interpretation"])
    logger.info("=" * 80)
    
    # Exit with success if gates pass
    all_gates_pass = all(report["gates"].values())
    logger.info(f"\nOverall stability: {'PASS ✅' if all_gates_pass else 'FAIL ⚠️'}")
    
    return 0 if all_gates_pass else 1


if __name__ == "__main__":
    sys.exit(main())
