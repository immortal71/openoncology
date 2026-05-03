"""Run the recurring validation discipline cycle.

This script enforces regular execution of:
  1) Hard clinical benchmark gate (locked metric: standard_precision_at_3)
  2) Blind external holdout generation
  3) Before/after oncologist diff generation for difficult cases

Usage:
    .venv\\Scripts\\python.exe scripts\\run_validation_cycle.py
    .venv\\Scripts\\python.exe scripts\\run_validation_cycle.py --n-cases 32 --seed 21

Exit code:
    0 when cycle completes and hard gate passes
    1 when cycle completes but hard gate fails, or a step errors
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, UTC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.blind_external_validation import run_blind_external_validation
from scripts.generate_oncologist_review_diff import main as run_diff
from scripts.hard_benchmark_gate import _main as run_hard_gate
from scripts.industry_grade_validation import run_industry_grade_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full validation discipline cycle")
    parser.add_argument("--n-cases", type=int, default=24, help="Blind holdout case count")
    parser.add_argument("--seed", type=int, default=11, help="Blind holdout RNG seed")
    parser.add_argument(
        "--profile",
        choices=["legacy_standard", "transparent_v1", "industry_v1"],
        default="transparent_v1",
        help="Blind benchmark profile",
    )
    args = parser.parse_args()

    hard_gate_rc = asyncio.run(run_hard_gate())

    blind_packet, key_packet = run_blind_external_validation(args.n_cases, args.seed, args.profile)
    blind_path = os.path.join(ROOT, "blind_review_packet.json")
    key_path = os.path.join(ROOT, "blind_review_key_scoring.json")

    with open(blind_path, "w", encoding="utf-8") as f:
        json.dump(blind_packet, f, indent=2)
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(key_packet, f, indent=2)

    diff_rc = run_diff()
    industry_report = run_industry_grade_validation()

    summary = {
        "run_at": datetime.now(UTC).isoformat(),
        "hard_benchmark_gate": "PASS" if hard_gate_rc == 0 else "FAIL",
        "blind_cases": blind_packet["n_cases"],
        "blind_metrics": key_packet["metrics"],
        "industry_validation": {
            "industry_grade_ready": industry_report["readiness_gates"]["industry_grade_ready"],
            "standard_precision_at_3": industry_report["metrics"]["standard_precision_at_3"],
            "standard_precision_at_3_ci95": industry_report["metrics"]["standard_precision_at_3_ci95"],
            "false_positive_rate": industry_report["metrics"]["false_positive_rate"],
            "sensitivity_case_count": industry_report["metrics"]["sensitivity_case_count"],
            "no_exact_leakage_pass": industry_report["readiness_gates"]["results"]["no_exact_leakage_pass"],
        },
        "diff_generated": diff_rc == 0,
    }

    summary_path = os.path.join(ROOT, "benchmark_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 72)
    print("VALIDATION DISCIPLINE CYCLE")
    print("=" * 72)
    print(f"Hard gate: {'PASS' if hard_gate_rc == 0 else 'FAIL'}")
    print(f"Blind profile: {blind_packet.get('benchmark_profile', 'legacy_standard')}")
    print(f"Blind holdout cases: {blind_packet['n_cases']}")
    print(f"Standard P@3: {key_packet['metrics']['standard_precision_at_3']:.3f}")
    print(f"Normalized P@3: {key_packet['metrics'].get('normalized_precision_at_3', 0.0):.3f}")
    print(f"Hit@3:        {key_packet['metrics']['hit_at_3']:.3f}")
    print(f"MRR:          {key_packet['metrics'].get('mrr', 0.0):.3f}")
    print(f"NDCG@3:       {key_packet['metrics'].get('ndcg_at_3', 0.0):.3f}")
    print(
        "Single-drug sensitivity fraction: "
        f"{key_packet['metrics'].get('single_drug_sensitivity_fraction', 0.0):.3f}"
    )
    print(f"Metric redundancy risk: {key_packet['metrics'].get('metric_redundancy_risk', False)}")
    print(f"False positives: {key_packet['metrics']['false_positives']}")
    print("Industry strict ready: ", industry_report["readiness_gates"]["industry_grade_ready"])
    print(
        "Industry strict Std P@3: "
        f"{industry_report['metrics']['standard_precision_at_3']:.3f} "
        f"(CI95 {industry_report['metrics']['standard_precision_at_3_ci95'][0]:.3f}-"
        f"{industry_report['metrics']['standard_precision_at_3_ci95'][1]:.3f})"
    )
    print(f"Cycle summary: {summary_path}")

    return 0 if hard_gate_rc == 0 and diff_rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
