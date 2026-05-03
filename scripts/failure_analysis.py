"""Hard benchmark failure analysis focused on ranking-logic root causes.

Run from project root:
    .venv\Scripts\python.exe scripts\failure_analysis.py
"""

from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.services.benchmark import run_hard_clinical_benchmark


async def _main() -> int:
    report = await run_hard_clinical_benchmark()

    print("=" * 72)
    print("HARD CLINICAL FAILURE ANALYSIS")
    print("=" * 72)
    print(f"Run at: {report.run_at}")
    print(f"API mode: {report.api_mode}")
    print(f"Cases: {report.n_cases} (sensitivity={report.n_sensitivity}, negatives={report.n_negative})")
    print(f"Standard P@3: {report.mean_standard_precision_at_3:.3f}")
    print(f"Hit@3: {report.hit_rate_at_3:.1%}")
    print(f"False positives: {report.false_positive_count}")

    print("\nRoot-cause counts:")
    for root, count in sorted(report.root_cause_counts.items()):
        print(f"  - {root}: {count}")

    failures = [r for r in report.case_results if not r.passed]
    if not failures:
        print("\nNo failed hard cases. Focus on incremental ranking-quality improvements.")
    else:
        print("\nFailed cases:")
        for r in failures:
            print(f"  - {r.case_id} [{r.difficulty}]")
            print(f"      root_cause: {r.root_cause}")
            print(f"      known: {r.known_drugs}")
            print(f"      top3:  {r.top3_drugs}")
            print(f"      std_p3={r.standard_precision_at_3:.3f} hit@3={r.hit_at_3}")

    print("\nRanking-logic remediation guidance:")
    print("  1. Prioritize ranking_miss_top3 and ordering_gap_within_top3 first.")
    print("  2. Tune evidence fusion / uncertainty handling before adding aliases.")
    print("  3. Keep resistance gate and no-drug thresholds conservative.")
    print("  4. Use live OncoKB as primary source; static table remains fallback.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
