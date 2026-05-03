"""Hard Clinical Benchmark quality gate.

Purpose:
- Run the difficult clinical benchmark subset regularly.
- Enforce conservative quality thresholds on STANDARD P@3.
- Print root-cause diagnostics for misses, focused on ranking behaviour.

Usage:
    .venv\\Scripts\\python.exe scripts\\hard_benchmark_gate.py

Exit codes:
    0 -> gate passed
    1 -> gate failed (threshold not met or false positives found)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, UTC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.services.benchmark import run_hard_clinical_benchmark
from api.services.oncokb_evidence import ensure_oncokb_table_loaded

LOCKED_PRIMARY_METRIC = "standard_precision_at_3"
TARGET_STD_P3 = 0.65
TARGET_HIT3 = 0.90
TARGET_FP = 0

ensure_oncokb_table_loaded()


def _print_failed_cases(report) -> None:
    failed = [r for r in report.case_results if not r.passed]
    if not failed:
        print("No hard-case failures detected.")
        return

    print("\nFailed cases:")
    for r in failed:
        print(f"  - {r.case_id}")
        print(f"      difficulty: {r.difficulty}")
        print(f"      root_cause: {r.root_cause}")
        print(f"      known: {r.known_drugs}")
        print(f"      top3:  {r.top3_drugs}")
        print(f"      std_p3={r.standard_precision_at_3:.3f}  hit@3={r.hit_at_3}")


def _print_root_cause_actions(report) -> None:
    print("\nRoot-cause actions (ranking-logic focused):")
    counts = report.root_cause_counts

    if counts.get("candidate_generation_gap", 0) > 0:
        print("  - candidate_generation_gap: improve candidate retrieval breadth before ranking.")
    if counts.get("ranking_miss_top3", 0) > 0:
        print("  - ranking_miss_top3: tune score fusion and resistance/penalty interactions.")
    if counts.get("ordering_gap_within_top3", 0) > 0:
        print("  - ordering_gap_within_top3: refine tie-breakers using confidence + uncertainty.")
    if counts.get("candidate_coverage_gap", 0) > 0:
        print("  - candidate_coverage_gap: increase recall from live evidence source, not aliases.")
    if counts.get("false_positive_high_confidence", 0) > 0:
        print("  - false_positive_high_confidence: tighten no-drug threshold and confidence gates.")


async def _main() -> int:
    report = await run_hard_clinical_benchmark()

    print("=" * 72)
    print("HARD CLINICAL BENCHMARK QUALITY GATE")
    print("=" * 72)
    print(report.summary())

    std_ok = report.mean_standard_precision_at_3 >= TARGET_STD_P3
    hit_ok = report.hit_rate_at_3 >= TARGET_HIT3
    fp_ok = report.false_positive_count <= TARGET_FP

    print("\nTargets:")
    print(f"  - Standard P@3 >= {TARGET_STD_P3:.2f}: {'PASS' if std_ok else 'FAIL'}")
    print(f"  - Hit@3 >= {TARGET_HIT3:.2f}: {'PASS' if hit_ok else 'FAIL'}")
    print(f"  - False positives <= {TARGET_FP}: {'PASS' if fp_ok else 'FAIL'}")

    _print_failed_cases(report)
    _print_root_cause_actions(report)

    artifact = {
        "run_at": datetime.now(UTC).isoformat(),
        "metric_lock": LOCKED_PRIMARY_METRIC,
        "targets": {
            "standard_precision_at_3": TARGET_STD_P3,
            "hit_at_3": TARGET_HIT3,
            "false_positives": TARGET_FP,
        },
        "actual": {
            "standard_precision_at_3": round(report.mean_standard_precision_at_3, 4),
            "hit_at_3": round(report.hit_rate_at_3, 4),
            "false_positives": report.false_positive_count,
            "n_cases": report.n_cases,
            "n_sensitivity": report.n_sensitivity,
            "n_negative": report.n_negative,
        },
        "by_difficulty": {
            key: {
                "standard_precision_at_3": round(report.by_difficulty_standard_p3[key], 4),
                "standard_precision_at_3_ceiling": round(
                    report.by_difficulty_standard_p3_ceiling.get(key, report.by_difficulty_standard_p3[key]),
                    4,
                ),
            }
            for key in sorted(report.by_difficulty_standard_p3)
        },
        "result": "PASS" if (std_ok and hit_ok and fp_ok) else "FAIL",
        "api_mode": report.api_mode,
    }
    out_path = os.path.join(ROOT, "hard_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Gate artifact: {out_path}")

    if std_ok and hit_ok and fp_ok:
        print("\nGate result: PASS")
        return 0

    print("\nGate result: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
