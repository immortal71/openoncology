"""Diagnose the one remaining ordering_gap_within_top3 case."""
import asyncio, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(ROOT, "api")
for p in (API_ROOT, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from api.services.benchmark import run_hard_clinical_benchmark
from api.services.oncokb_evidence import ensure_oncokb_table_loaded

ensure_oncokb_table_loaded()

async def main():
    report = await run_hard_clinical_benchmark()
    print("=== All non-full-coverage cases ===")
    for r in report.case_results:
        rc = getattr(r, "root_cause", "?")
        if rc not in ("full_top3_coverage", "negative_control_pass", "single_drug_denominator_penalty"):
            print(f"\ncase_id:    {r.case_id}")
            print(f"root_cause: {rc}")
            print(f"known:      {getattr(r, 'known_drugs', '?')}")
            print(f"top3:       {getattr(r, 'top3_drugs', '?')}")
            print(f"p3:         {getattr(r, 'standard_precision_at_3', '?'):.3f}  hit@3={getattr(r, 'hit_at_3', '?')}")

asyncio.run(main())
