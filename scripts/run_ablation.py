"""Ablation Study Runner — OpenOncology

Runs the full evidence-source ablation study against the gold-standard
benchmark cases and prints a formatted results table showing which evidence
sources contribute most to ranking quality.

Usage (from project root, with .venv active):
    python scripts/run_ablation.py
    python scripts/run_ablation.py --level1-only
    python scripts/run_ablation.py --output ablation_results.json

The study zeroes out each evidence source in turn and measures the drop in
Precision@3 and MRR.  Negative Δ = removing this source hurts performance
(source is valuable).  Near-zero Δ = marginal contribution in this test set.

Notes:
  - Requires OpenTargets API access for full results.
  - In offline mode (no OpenTargets access), only OncoKB-injected drugs are
    evaluated, which underestimates the contribution of OpenTargets and DiffDock.
  - Run time: ~5–15 minutes depending on API latency and case count.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_api_dir = os.path.join(_project_root, "api")

for _p in (_api_dir, _project_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("run_ablation")


def _build_offline_cases(
    gold_cases: list[dict],
) -> list[dict]:
    """Build a synthetic candidate list per case using only the OncoKB table.

    Used when OpenTargets API is not available.  The candidate pool is derived
    solely from the static OncoKB evidence table — so the benchmark is biased
    towards OncoKB and underweights OpenTargets/DiffDock, but it gives a fast
    offline estimate.
    """
    from api.services.oncokb_evidence import get_all_drugs_for_variant

    synthetic: list[dict] = []
    for case in gold_cases:
        gene = case["gene"]
        variant = case["variant"]
        variant_drugs = get_all_drugs_for_variant(gene, variant, alphamissense_score=1.0)
        if not variant_drugs:
            continue
        case_copy = dict(case)
        case_copy["_synthetic_candidates"] = [
            {
                "drug_name": drug.title(),
                "oncokb_level": level,
                "opentargets_score": 0.7 if level == "LEVEL_1" else (0.5 if level == "LEVEL_2" else 0.3),
                "is_approved": level == "LEVEL_1",
                "max_phase": 4 if level == "LEVEL_1" else 3,
                "binding_score": None,
                "alphamissense_score": None,
                "civic_score": None,
            }
            for drug, level in variant_drugs.items()
            if "R" not in level  # exclude pure resistance entries from candidate pool
        ]
        synthetic.append(case_copy)
    return synthetic


async def _run_offline_ablation(
    gold_cases: list[dict],
) -> dict:
    """Run ablation study in offline mode using only the OncoKB static table."""
    from api.ai.ranking import rank_candidates
    from api.ai.ranking_config import RankingConfig, EvidenceWeights
    from api.services.benchmark import (
        AblationResult, AblationStudyReport,
        precision_at_k, hit_at_k, mean_reciprocal_rank, ndcg_at_k,
    )

    offline_cases = _build_offline_cases(gold_cases)
    if not offline_cases:
        logger.error("No offline cases could be built — OncoKB table may be empty.")
        return {"error": "No offline cases available."}

    fields = ["binding", "opentargets", "oncokb", "alphamissense", "clinical_phase", "civic"]
    source_labels = {
        "binding": "DiffDock", "opentargets": "OpenTargets", "oncokb": "OncoKB",
        "alphamissense": "AlphaMissense", "clinical_phase": "ClinicalPhase", "civic": "CIViC",
    }

    def _avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _score_case(case: dict, cfg: RankingConfig) -> tuple[float, float, bool]:
        candidates = [dict(c) for c in case.get("_synthetic_candidates", [])]
        if not candidates:
            return 0.0, 0.0, False
        ranked = rank_candidates(candidates, cfg)
        names = [d.get("drug_name", "") for d in ranked if d.get("drug_name")]
        known = case["known_drugs"]
        return (
            precision_at_k(names, known, 3),
            mean_reciprocal_rank(names, known),
            hit_at_k(names, known, 3),
        )

    def _equal_redistribute(zero_field: str) -> EvidenceWeights:
        remaining = [f for f in fields if f != zero_field]
        share = 1.0 / len(remaining)
        return EvidenceWeights(**{f: 0.0 if f == zero_field else share for f in fields})

    # Full model
    full_cfg = RankingConfig()
    full_scores = [_score_case(c, full_cfg) for c in offline_cases]
    full_p3 = _avg([s[0] for s in full_scores])
    full_mrr = _avg([s[1] for s in full_scores])
    full_h3 = _avg([1.0 if s[2] else 0.0 for s in full_scores])

    ablation_results: list[AblationResult] = []
    for field in fields:
        ab_weights = _equal_redistribute(field)
        ab_cfg = RankingConfig(weights=ab_weights)
        ab_scores = [_score_case(c, ab_cfg) for c in offline_cases]
        ab_p3 = _avg([s[0] for s in ab_scores])
        ab_mrr = _avg([s[1] for s in ab_scores])
        ab_h3 = _avg([1.0 if s[2] else 0.0 for s in ab_scores])
        ablation_results.append(AblationResult(
            ablated_source=source_labels[field],
            mean_precision_at_3=round(ab_p3, 4),
            mean_mrr=round(ab_mrr, 4),
            hit_rate_at_3=round(ab_h3, 4),
            delta_precision_at_3=round(ab_p3 - full_p3, 4),
            delta_mrr=round(ab_mrr - full_mrr, 4),
            note="offline-mode (OncoKB table only)",
        ))

    report = AblationStudyReport(
        run_at=datetime.now().isoformat(),
        n_cases=len(offline_cases),
        full_model_precision_at_3=round(full_p3, 4),
        full_model_mrr=round(full_mrr, 4),
        full_model_hit_at_3=round(full_h3, 4),
        results=ablation_results,
    )
    return report


async def main(args: argparse.Namespace) -> None:
    from api.services.benchmark import (
        GOLD_STANDARD_CASES, LEVEL_1_CASES, EXTENDED_GOLD_STANDARD_CASES,
    )

    if args.level1_only:
        cases = LEVEL_1_CASES
        label = "Level-1 only"
    elif args.extended:
        cases = GOLD_STANDARD_CASES + EXTENDED_GOLD_STANDARD_CASES
        label = "Full extended set"
    else:
        cases = GOLD_STANDARD_CASES
        label = "Core gold-standard set"

    logger.info("Case set: %s (%d cases)", label, len(cases))

    # Try live API mode first, fall back to offline
    try:
        from api.services.benchmark import run_ablation_sync
        # Quick connectivity check — if OpenTargets is not reachable, fall back
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.platform.opentargets.org/api/v4/graphql", timeout=5.0)
            api_reachable = resp.status_code in (200, 400)
    except Exception:
        api_reachable = False

    if api_reachable and not args.offline:
        logger.info("OpenTargets API reachable — running full online ablation study.")
        from api.services.benchmark import run_ablation_study
        report = await run_ablation_study(cases)
    else:
        logger.info("Running in OFFLINE mode (OncoKB table only). "
                    "Results will underestimate OpenTargets and DiffDock contributions.")
        report = await _run_offline_ablation(cases)

    if isinstance(report, dict):
        print(f"\nError: {report.get('error', 'Unknown error')}")
        return

    # ── Print formatted table ──────────────────────────────────────────────
    print("\n" + "=" * 76)
    print("  OPENONCOLOGY — EVIDENCE SOURCE ABLATION STUDY")
    print(f"  Run at: {report.run_at}   |   Cases: {report.n_cases}   |   {label}")
    print("=" * 76)
    print(f"\n  Full model:  P@3 = {report.full_model_precision_at_3:.3f}  |  "
          f"MRR = {report.full_model_mrr:.3f}  |  Hit@3 = {report.full_model_hit_at_3:.1%}")
    print(f"\n  {'Source':<20} {'P@3':>6} {'Hit@3':>7} {'MRR':>7}  {'ΔP@3':>7}  {'ΔMRR':>7}  Impact")
    print("  " + "─" * 74)

    for r in sorted(report.results, key=lambda x: x.delta_mrr):
        if abs(r.delta_mrr) > 0.05:
            impact = "★★★ HIGH"
        elif abs(r.delta_mrr) > 0.02:
            impact = " ★★  MEDIUM"
        else:
            impact = "  ★  LOW"
        print(
            f"  {r.ablated_source:<20} {r.mean_precision_at_3:>6.3f} "
            f"{r.hit_rate_at_3:>7.1%} {r.mean_mrr:>7.3f} "
            f"{r.delta_precision_at_3:>+7.3f} {r.delta_mrr:>+7.3f}  {impact}"
        )

    print("\n  Negative ΔP@3 / ΔMRR = source is valuable (removing it hurts ranking).")
    print("  Near-zero delta = low marginal contribution (data often missing in this set).")

    print("\n  Interpretation:")
    for r in sorted(report.results, key=lambda x: x.delta_mrr):
        if r.delta_mrr < -0.05:
            print(f"    • {r.ablated_source}: CRITICAL contributor — do not remove or reduce weight.")
        elif r.delta_mrr < -0.02:
            print(f"    • {r.ablated_source}: Useful — provides meaningful signal in current test set.")
        elif r.delta_mrr > 0.01:
            print(f"    • {r.ablated_source}: Marginal/noisy — consider reducing weight or reviewing data quality.")
        else:
            print(f"    • {r.ablated_source}: Low contribution in offline mode — may improve with live API data.")

    print("\n  Benchmark Limitations:")
    print("    - Online mode: uses OpenTargets API + OncoKB table. DiffDock/binding scores absent.")
    print("    - Offline mode: OncoKB table only — OpenTargets/DiffDock contribution underestimated.")
    print("    - VUS cases and resistance-only mutations are NOT included in sensitivity metrics.")
    print("    - No prospective clinical validation has been performed.")
    print("=" * 76 + "\n")

    if args.output:
        import dataclasses
        data = {
            "run_at": report.run_at,
            "n_cases": report.n_cases,
            "case_set": label,
            "full_model": {
                "precision_at_3": report.full_model_precision_at_3,
                "mrr": report.full_model_mrr,
                "hit_at_3": report.full_model_hit_at_3,
            },
            "ablation_results": [
                {
                    "source": r.ablated_source,
                    "precision_at_3": r.mean_precision_at_3,
                    "mrr": r.mean_mrr,
                    "hit_at_3": r.hit_rate_at_3,
                    "delta_p3": r.delta_precision_at_3,
                    "delta_mrr": r.delta_mrr,
                    "note": getattr(r, "note", ""),
                }
                for r in report.results
            ],
        }
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Results written to %s", args.output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run OpenOncology evidence source ablation study.")
    parser.add_argument("--level1-only", action="store_true", help="Restrict to OncoKB Level 1 cases only.")
    parser.add_argument("--extended", action="store_true", help="Include extended gold-standard cases.")
    parser.add_argument("--offline", action="store_true", help="Force offline mode (OncoKB table only).")
    parser.add_argument("--output", metavar="FILE", help="Write JSON results to FILE.")
    args = parser.parse_args()
    asyncio.run(main(args))
