"""Industry-grade external validation audit.

This script is intentionally strict and avoids benchmark inflation tricks:
- Uses full external holdout cohort (no random cherry-picking by default).
- Uses standard_precision_at_3 as primary metric.
- Reports 95% confidence intervals for key metrics.
- Runs train/eval leakage diagnostics.
- Emits explicit readiness gates instead of vanity composites.

Usage:
    .venv\\Scripts\\python.exe scripts\\industry_grade_validation.py
    .venv\\Scripts\\python.exe scripts\\industry_grade_validation.py --max-cases 120
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# CIViC is optional for strict audit reproducibility; opt-in with env var.
USE_CIVIC = os.getenv("INDUSTRY_VALIDATION_USE_CIVIC", "0") == "1"

from api.ai.ranking import rank_candidates
from api.services.benchmark import (
    ADDITIONAL_VALIDATION_CASES,
    HARD_CLINICAL_CASES,
    hit_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    standard_precision_at_k,
)
from api.services.oncokb_evidence import get_all_drugs_for_variant_live


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


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    phat = successes / total
    denom = 1.0 + (z * z / total)
    center = (phat + (z * z / (2.0 * total))) / denom
    margin = (z / denom) * math.sqrt((phat * (1.0 - phat) / total) + (z * z / (4.0 * total * total)))
    return (max(0.0, center - margin), min(1.0, center + margin))


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


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _fetch_civic_levels_sync(gene: str, variant: str) -> dict[str, str]:
    try:
        from api.services.civic import get_civic_evidence
    except Exception:
        return {}

    async def _run() -> dict[str, str]:
        try:
            rows = await get_civic_evidence(gene, variant)
        except Exception:
            # CIViC is auxiliary evidence. If unavailable, proceed without it.
            return {}
        if not rows:
            return {}
        rank = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        levels: dict[str, str] = {}
        for row in rows:
            level = str(row.get("evidenceLevel", "")).upper().strip()
            if level not in rank:
                continue
            for d in row.get("drugs", []) or []:
                name = str((d or {}).get("name", "")).strip()
                if not name:
                    continue
                norm = _norm_drug(name)
                prev = levels.get(norm)
                if prev is None or rank[level] > rank.get(prev, 0):
                    levels[norm] = level
        return levels

    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        except Exception:
            return {}
        finally:
            loop.close()
    except Exception:
        return {}


def _build_candidates(case: dict[str, Any]) -> list[dict[str, Any]]:
    gene = case["gene"]
    variant = case["variant"]
    cancer_type = case.get("cancer_type")
    level_map = get_all_drugs_for_variant_live(gene, variant, cancer_type)
    civic_levels = _fetch_civic_levels_sync(gene, variant) if USE_CIVIC else {}
    vaf = case.get("vaf")
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
                "opentargets_score": None,
                "is_approved": level_upper == "LEVEL_1",
                "max_phase": 4 if level_upper == "LEVEL_1" else (3 if level_upper == "LEVEL_2" else 2),
                "binding_score": None,
                "alphamissense_score": None,
                "civic_score": civic_levels.get(_norm_drug(drug_name)),
                "vaf": vaf,
                "target_gene": gene,
                "co_mutated_genes": co_mutated_genes,
            }
        )
    return rank_candidates(candidates)


def _get_external_cases(max_cases: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dev_keys = {_case_key(c) for c in HARD_CLINICAL_CASES}
    full_external = [c for c in ADDITIONAL_VALIDATION_CASES if _case_key(c) not in dev_keys]

    # Deterministic order for reproducibility, no random sampling by default.
    full_external = sorted(full_external, key=lambda c: str(c.get("case_id", "")))
    selected = full_external if max_cases is None else full_external[:max_cases]

    overlap_exact = [c for c in selected if _case_key(c) in dev_keys]
    dev_gene_variant = {(str(c.get("gene", "")), str(c.get("variant", ""))) for c in HARD_CLINICAL_CASES}
    eval_gene_variant = {(str(c.get("gene", "")), str(c.get("variant", ""))) for c in selected}
    gv_overlap = len(dev_gene_variant & eval_gene_variant)

    leakage = {
        "dev_cases": len(HARD_CLINICAL_CASES),
        "external_pool_cases": len(full_external),
        "external_selected_cases": len(selected),
        "exact_case_overlap_count": len(overlap_exact),
        "gene_variant_overlap_count": gv_overlap,
        "gene_variant_overlap_rate": round(gv_overlap / len(eval_gene_variant), 4) if eval_gene_variant else 0.0,
        "exact_overlap_pass": len(overlap_exact) == 0,
    }
    return selected, leakage


def run_industry_grade_validation(max_cases: int | None = None) -> dict[str, Any]:
    cases, leakage = _get_external_cases(max_cases=max_cases)

    std_p3_vals: list[float] = []
    hit3_vals: list[float] = []
    mrr_vals: list[float] = []
    ndcg3_vals: list[float] = []
    fp_count = 0
    sensitivity_case_count = 0
    specificity_case_count = 0
    sensitivity_cases: list[dict[str, Any]] = []

    by_diff: dict[str, list[float]] = {}
    by_cancer: dict[str, list[float]] = {}

    for case in cases:
        expect_empty = bool(case.get("expect_empty", False))
        ranked = _build_candidates(case)
        ranked_names = [r.get("drug_name", "") for r in ranked if r.get("drug_name")]
        top3 = ranked[:3]

        if expect_empty:
            specificity_case_count += 1
            high_conf = [r for r in top3 if r.get("rank_score", 0) > 0.25 and r.get("oncokb_level")]
            if high_conf:
                fp_count += 1
            continue

        known = case.get("known_drugs", []) or []
        sensitivity_case_count += 1
        sensitivity_cases.append(case)

        std_p3 = standard_precision_at_k(ranked_names, known, 3)
        h3 = 1.0 if hit_at_k(ranked_names, known, 3) else 0.0
        mrr = mean_reciprocal_rank(ranked_names, known)
        ndcg3 = ndcg_at_k(ranked_names, known, 3)

        std_p3_vals.append(std_p3)
        hit3_vals.append(h3)
        mrr_vals.append(mrr)
        ndcg3_vals.append(ndcg3)

        diff = str(case.get("difficulty", "UNKNOWN"))
        by_diff.setdefault(diff, []).append(std_p3)
        ct = str(case.get("cancer_type", "UNKNOWN"))
        by_cancer.setdefault(ct, []).append(std_p3)

    fp_rate = (fp_count / specificity_case_count) if specificity_case_count else 0.0
    hit3_success = sum(1 for v in hit3_vals if v >= 1.0)

    standard_p3_mean = _avg(std_p3_vals)
    standard_p3_ci = _mean_ci_normal_approx(std_p3_vals)
    hit3_ci = _wilson_ci(hit3_success, len(hit3_vals))

    # Structural ceiling: the theoretical maximum Standard P@3 given the case mix.
    # A case with 1 known drug has a ceiling of 0.333; a case with ≥3 known drugs
    # has a ceiling of 1.000. Measuring performance as a fraction of the ceiling
    # is the honest way to compare across evaluation sets with different single-drug fractions.
    case_ceilings = [
        min(3, len(case.get("known_drugs") or [])) / 3.0
        for case in sensitivity_cases
    ]
    structural_ceiling = _avg(case_ceilings)
    multi_drug_fraction = (
        sum(1 for c in sensitivity_cases if len(c.get("known_drugs") or []) > 1) / len(sensitivity_cases)
        if sensitivity_cases
        else 0.0
    )
    l3_l4_case_count = sum(1 for c in sensitivity_cases if str(c.get("difficulty", "")) == "L3_L4")
    # Ceiling-normalised Standard P@3: how much of the achievable ceiling is captured.
    ceiling_normalised_p3 = (standard_p3_mean / structural_ceiling) if structural_ceiling > 0 else 0.0
    ceiling_normalised_p3_ci: tuple[float, float]
    if structural_ceiling > 0:
        normalised_vals = [v / structural_ceiling for v in std_p3_vals]
        ceiling_normalised_p3_ci = _mean_ci_normal_approx(normalised_vals)
    else:
        ceiling_normalised_p3_ci = (0.0, 0.0)

    # Conservative readiness gates for an "industry-grade" claim.
    # Primary gate: ceiling-normalised P@3 ≥ 0.80 (captures ≥80% of achievable score).
    # This is robust to single-drug case saturation; a system that always gets the
    # one correct drug for 1-drug cases AND gets 2/3 for 2-drug cases will score ~0.77
    # raw but ~0.93 normalised — correctly flagged as high-quality.
    CEILING_NORM_THRESHOLD = 0.85
    gate_defs = {
        # Sample size floor: industry claim should not be made from a few dozen sensitivity cases.
        "min_external_sensitivity_cases": 80,
        # Cohort-quality floors to prevent passing on an easy single-drug-heavy pool.
        "min_structural_ceiling": 0.62,
        "min_multi_drug_fraction": 0.60,
        "min_l3_l4_case_count": 20,
        # Statistical confidence floor on the ceiling-normalised metric.
        # The raw CI lower cannot exceed the structural ceiling, so we gate on the
        # normalised CI lower instead.  Requires CI95 lower of (norm P@3) ≥ 0.80.
        "min_ceiling_normalised_p3_ci95_lower": 0.80,
        # Guardrail against near-duplicate dev/eval biology.
        "max_gene_variant_overlap_rate": 0.25,
        "max_false_positive_rate": 0.05,
        "min_ceiling_normalised_p3": CEILING_NORM_THRESHOLD,
        "min_hit_at_3": 0.80,
        # Raw P@3 floor kept as a sanity floor only (prevents artificially low ceilings gaming the norm).
        "min_raw_standard_p3_floor": 0.45,
    }
    gates = {
        "external_sample_size_pass": sensitivity_case_count >= gate_defs["min_external_sensitivity_cases"],
        "structural_ceiling_pass": structural_ceiling >= gate_defs["min_structural_ceiling"],
        "multi_drug_fraction_pass": multi_drug_fraction >= gate_defs["min_multi_drug_fraction"],
        "l3_l4_density_pass": l3_l4_case_count >= gate_defs["min_l3_l4_case_count"],
        "ceiling_normalised_p3_ci95_lower_pass": ceiling_normalised_p3_ci[0] >= gate_defs["min_ceiling_normalised_p3_ci95_lower"],
        "gene_variant_overlap_pass": leakage.get("gene_variant_overlap_rate", 1.0) <= gate_defs["max_gene_variant_overlap_rate"],
        "false_positive_rate_pass": fp_rate <= gate_defs["max_false_positive_rate"],
        "ceiling_normalised_p3_pass": ceiling_normalised_p3 >= gate_defs["min_ceiling_normalised_p3"],
        "hit_at_3_pass": _avg(hit3_vals) >= gate_defs["min_hit_at_3"],
        "raw_p3_floor_pass": standard_p3_mean >= gate_defs["min_raw_standard_p3_floor"],
        "no_exact_leakage_pass": bool(leakage.get("exact_overlap_pass", False)),
    }
    industry_grade_ready = all(gates.values())

    top_cancer = sorted(by_cancer.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    stratified_cancer = {
        k: {
            "n": len(v),
            "standard_precision_at_3": round(_avg(v), 4),
        }
        for k, v in top_cancer
    }
    stratified_diff = {
        k: {
            "n": len(v),
            "standard_precision_at_3": round(_avg(v), 4),
        }
        for k, v in sorted(by_diff.items())
    }

    return {
        "run_at": datetime.now(UTC).isoformat(),
        "profile": "industry_strict_v1",
        "primary_metric": "standard_precision_at_3",
        "metrics": {
            "standard_precision_at_3": round(standard_p3_mean, 4),
            "standard_precision_at_3_ci95": [round(standard_p3_ci[0], 4), round(standard_p3_ci[1], 4)],
            "structural_ceiling": round(structural_ceiling, 4),
            "multi_drug_fraction": round(multi_drug_fraction, 4),
            "l3_l4_case_count": l3_l4_case_count,
            "ceiling_normalised_p3": round(ceiling_normalised_p3, 4),
            "ceiling_normalised_p3_ci95": [
                round(ceiling_normalised_p3_ci[0], 4),
                round(ceiling_normalised_p3_ci[1], 4),
            ],
            "hit_at_3": round(_avg(hit3_vals), 4),
            "hit_at_3_ci95": [round(hit3_ci[0], 4), round(hit3_ci[1], 4)],
            "mrr": round(_avg(mrr_vals), 4),
            "ndcg_at_3": round(_avg(ndcg3_vals), 4),
            "false_positives": fp_count,
            "false_positive_rate": round(fp_rate, 4),
            "sensitivity_case_count": sensitivity_case_count,
            "specificity_case_count": specificity_case_count,
        },
        "leakage_diagnostics": leakage,
        "readiness_gates": {
            "definitions": gate_defs,
            "results": gates,
            "industry_grade_ready": industry_grade_ready,
        },
        "stratified": {
            "by_difficulty": stratified_diff,
            "by_cancer_type_top10": stratified_cancer,
        },
        "notes": [
            "No synthetic weighting/composite score is used.",
            "No random enrichment sampling is used by default.",
            "Industry-grade claim requires all readiness gates to pass.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict industry-grade external validation audit")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional cap on external cases; default evaluates full external pool",
    )
    args = parser.parse_args()

    report = run_industry_grade_validation(max_cases=args.max_cases)
    out_path = os.path.join(ROOT, "industry_validation_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    m = report["metrics"]
    rg = report["readiness_gates"]
    print("=" * 72)
    print("INDUSTRY-GRADE VALIDATION AUDIT (STRICT)")
    print("=" * 72)
    print(f"Primary metric: Standard P@3")
    print(
        f"Standard P@3:        {m['standard_precision_at_3']:.3f} "
        f"(95% CI {m['standard_precision_at_3_ci95'][0]:.3f}-{m['standard_precision_at_3_ci95'][1]:.3f})"
    )
    print(f"Structural ceiling:  {m['structural_ceiling']:.3f}  (case-mix ceiling for this eval set)")
    print(f"Multi-drug fraction: {m['multi_drug_fraction']:.3f}  (sensitivity cases with >1 known drug)")
    print(f"L3/L4 cases:         {m['l3_l4_case_count']}  (hard-evidence density)")
    print(
        f"Ceiling-norm P@3:    {m['ceiling_normalised_p3']:.3f} "
        f"(95% CI {m['ceiling_normalised_p3_ci95'][0]:.3f}-{m['ceiling_normalised_p3_ci95'][1]:.3f})"
    )
    print(
        f"Hit@3:               {m['hit_at_3']:.3f} "
        f"(95% CI {m['hit_at_3_ci95'][0]:.3f}-{m['hit_at_3_ci95'][1]:.3f})"
    )
    print(f"MRR:                 {m['mrr']:.3f}")
    print(f"NDCG@3:              {m['ndcg_at_3']:.3f}")
    print(f"FP rate:             {m['false_positive_rate']:.3f} ({m['false_positives']} FP)")
    print(f"Sensitivity n:{m['sensitivity_case_count']}  Specificity n:{m['specificity_case_count']}")
    print("Leakage exact overlap pass:", report["leakage_diagnostics"]["exact_overlap_pass"])
    print(
        "Gene/variant overlap rate:",
        report["leakage_diagnostics"].get("gene_variant_overlap_rate", 0.0),
    )
    print("Industry-grade ready:", rg["industry_grade_ready"])
    failed = [name for name, passed in rg.get("results", {}).items() if not passed]
    if failed:
        print("Failed gates:", ", ".join(sorted(failed)))
    print(f"Report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
