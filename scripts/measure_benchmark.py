r"""Measure actual benchmark metrics: sensitivity P@3 and specificity FP-rate.

Run from project root:
    .venv\Scripts\python.exe scripts\measure_benchmark.py
    .venv\Scripts\python.exe scripts\measure_benchmark.py --hard-only

Options:
    --hard-only   Run the Hard Clinical Benchmark subset only.
                  Uses STANDARD P@3 (denominator=3, not normalised) to expose
                  multi-drug coverage gaps.
    --static-table  Force static curated table only.
                    Default mode is live-API-first OncoKB lookup.
"""
from __future__ import annotations
import asyncio
import statistics
import sys, os, json, argparse, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.services.benchmark import (
    GOLD_STANDARD_CASES, LEVEL_1_CASES, VUS_NEGATIVE_CASES, SENSITIVITY_CASES,
    ADDITIONAL_VALIDATION_CASES, HARD_CLINICAL_CASES, HARD_SENSITIVITY_CASES, HARD_NEGATIVE_CASES,
    precision_at_k, hit_at_k, mean_reciprocal_rank,
)
from api.ai.ranking import rank_candidates
from api.ai.ranking_config import RankingConfig
from api.services.oncokb_evidence import (
    ensure_oncokb_table_loaded,
    get_all_drugs_for_variant_live_with_metadata,
    get_all_drugs_for_variant_with_metadata,
)
from api.services.civic import get_civic_evidence

parser = argparse.ArgumentParser(description="OpenOncology offline benchmark")
parser.add_argument("--hard-only", action="store_true", help="Run Hard Clinical Benchmark subset only")
parser.add_argument(
    "--static-table",
    action="store_true",
    help="Force static curated table only (default is live-API-first)",
)
args = parser.parse_args()

ensure_oncokb_table_loaded()

# Choose the drug lookup function (default live-first).
_drug_lookup_with_meta = (
    get_all_drugs_for_variant_with_metadata
    if args.static_table
    else get_all_drugs_for_variant_live_with_metadata
)

# Standard P@3 always uses denominator=3 (not normalised) for honest comparison
_STANDARD_DENOM = True


def _norm_drug(name: str) -> str:
    return re.sub(r"[\s\-.]", "", str(name).lower())


def _get_civic_levels_sync(gene: str, variant: str) -> dict[str, str]:
    async def _fetch() -> dict[str, str]:
        rows = await get_civic_evidence(gene, variant)
        if not rows:
            return {}
        rank = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        out: dict[str, str] = {}
        for row in rows:
            level = str(row.get("evidenceLevel", "")).upper().strip()
            if level not in rank:
                continue
            for d in row.get("drugs", []) or []:
                n = str((d or {}).get("name", "")).strip()
                if not n:
                    continue
                norm = _norm_drug(n)
                prev = out.get(norm)
                if prev is None or rank[level] > rank.get(prev, 0):
                    out[norm] = level
        return out

    try:
        return asyncio.run(_fetch())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_fetch())
        finally:
            loop.close()


def build_candidates(
    gene: str,
    variant: str,
    cancer_type: str | None = None,
    alphamissense_score: float | None = None,
) -> list[dict]:
    if args.static_table:
        meta = _drug_lookup_with_meta(
            gene,
            variant,
            alphamissense_score=alphamissense_score,
        )
    else:
        meta = _drug_lookup_with_meta(
            gene,
            variant,
            cancer_type,
            alphamissense_score=alphamissense_score,
        )
    drugs = dict(meta.get("drug_levels") or {})
    fallback_drugs = {_norm_drug(d) for d in (meta.get("gene_fallback_drugs") or [])}
    if not drugs:
        return []
    civic_levels = _get_civic_levels_sync(gene, variant)
    return [
        {
            "drug_name": d.title(),
            "oncokb_level": lv,
            "opentargets_score": None,
            "is_approved": lv == "LEVEL_1",
            "max_phase": 4 if lv == "LEVEL_1" else 3,
            "binding_score": None,
            "alphamissense_score": alphamissense_score,
            "civic_score": civic_levels.get(_norm_drug(d)),
            "oncokb_gene_fallback": _norm_drug(d) in fallback_drugs,
        }
        for d, lv in drugs.items()
        if "R" not in lv   # exclude resistance entries from candidate pool
    ]


def avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _build_cfg_with_weights(binding: float, opentargets: float, oncokb: float) -> RankingConfig:
    cfg = RankingConfig()
    cfg.weights.binding = binding
    cfg.weights.opentargets = opentargets
    cfg.weights.oncokb = oncokb
    cfg.weights.validate()
    return cfg


def _evaluate_case_p3(case: dict, cfg_local: RankingConfig) -> float:
    cands = build_candidates(
        case["gene"],
        case["variant"],
        case.get("cancer_type"),
        case.get("alphamissense_score"),
    )
    if not cands:
        return 0.0
    ranked = rank_candidates(cands, cfg=cfg_local)
    names = [d.get("drug_name", "") for d in ranked]
    return precision_at_k(names, case["known_drugs"], 3)


def _cross_validate_p3(cases: list[dict], cfg_local: RankingConfig, folds: int = 5) -> dict:
    usable = [c for c in cases if c.get("known_drugs")]
    usable = sorted(usable, key=lambda c: c.get("case_id", ""))
    if not usable:
        return {"fold_scores": [], "mean": 0.0, "std": 0.0, "n_cases": 0}

    fold_bins: list[list[dict]] = [[] for _ in range(max(folds, 1))]
    for i, case in enumerate(usable):
        fold_bins[i % len(fold_bins)].append(case)

    fold_scores: list[float] = []
    for fold in fold_bins:
        if not fold:
            continue
        fold_p3 = [_evaluate_case_p3(case, cfg_local) for case in fold]
        fold_scores.append(avg(fold_p3))

    return {
        "fold_scores": [round(v, 4) for v in fold_scores],
        "mean": round(avg(fold_scores), 4),
        "std": round(statistics.pstdev(fold_scores), 4) if len(fold_scores) > 1 else 0.0,
        "n_cases": len(usable),
    }


def _holdout_8020_p3(cases: list[dict], cfg_local: RankingConfig) -> dict:
    usable = [c for c in cases if c.get("known_drugs")]
    usable = sorted(usable, key=lambda c: c.get("case_id", ""))
    if not usable:
        return {"train_n": 0, "val_n": 0, "train_p3": 0.0, "val_p3": 0.0}

    split_idx = max(1, int(len(usable) * 0.8))
    train_cases = usable[:split_idx]
    val_cases = usable[split_idx:]
    train_p3 = avg([_evaluate_case_p3(case, cfg_local) for case in train_cases])
    val_p3 = avg([_evaluate_case_p3(case, cfg_local) for case in val_cases]) if val_cases else 0.0

    return {
        "train_n": len(train_cases),
        "val_n": len(val_cases),
        "train_p3": round(train_p3, 4),
        "val_p3": round(val_p3, 4),
    }


cfg = RankingConfig()

# Cross-validated diagnostics to detect overfitting and compare weight sets.
_baseline_cfg = _build_cfg_with_weights(binding=0.25, opentargets=0.15, oncokb=0.30)
_tuned_cfg = _build_cfg_with_weights(binding=0.15, opentargets=0.15, oncokb=0.40)
cv_baseline = _cross_validate_p3(SENSITIVITY_CASES, _baseline_cfg, folds=5)
cv_tuned = _cross_validate_p3(SENSITIVITY_CASES, _tuned_cfg, folds=5)
holdout_tuned = _holdout_8020_p3(SENSITIVITY_CASES, _tuned_cfg)

print("[Cross-validation diagnostics]")
print(
    f"  baseline (DiffDock=0.25, OncoKB=0.30): "
    f"P@3={cv_baseline['mean']:.3f} ± {cv_baseline['std']:.3f} (5-fold)"
)
print(
    f"  tuned    (DiffDock=0.15, OncoKB=0.40): "
    f"P@3={cv_tuned['mean']:.3f} ± {cv_tuned['std']:.3f} (5-fold)"
)
print(
    f"  tuned 80/20 split: train P@3={holdout_tuned['train_p3']:.3f} "
    f"(n={holdout_tuned['train_n']}), val P@3={holdout_tuned['val_p3']:.3f} "
    f"(n={holdout_tuned['val_n']})"
)

# ════════════════════════════════════════════════════════════════════════
# HARD CLINICAL BENCHMARK (--hard-only mode)
# Uses STANDARD P@3 (denominator=3) — NOT normalised.
# This is the honest, conservative metric for multi-drug coverage quality.
# ════════════════════════════════════════════════════════════════════════
if args.hard_only:
    print("=" * 60)
    print("  HARD CLINICAL BENCHMARK  (STANDARD P@3, denominator=3)")
    print("  Categories: multi-drug, conflicting evidence, low purity,")
    print("  refractory, rare/complex cases.")
    print("  Pass thresholds: Hit@3 ≥ 0.80, Std P@3 ≥ 0.45, FP = 0")
    print("=" * 60)
    api_mode = "static table" if args.static_table else "live API"
    print(f"  OncoKB source: {api_mode}\n")

    hard_p3_std: list[float] = []
    hard_h3: list[float] = []
    hard_fp = 0

    by_category: dict[str, list[float]] = {}

    for case in HARD_CLINICAL_CASES:
        cat = case.get("difficulty", "UNKNOWN")
        expect_empty = case.get("expect_empty", False)
        cands = build_candidates(
            case["gene"],
            case["variant"],
            case.get("cancer_type"),
            case.get("alphamissense_score"),
        )

        if expect_empty:
            # Negative control: any high-confidence drug is a false positive
            if cands:
                ranked = rank_candidates(cands, cfg=cfg)
                top3 = ranked[:3]
                high_conf = [d for d in top3 if d.get("rank_score", 0) > 0.25 and d.get("oncokb_level")]
                if high_conf:
                    hard_fp += 1
                    print(f"  [FP] {case['case_id']}: returned {[d['drug_name'] for d in high_conf]}")
            continue

        known = case.get("known_drugs", [])
        if not cands:
            print(f"  [MISS] {case['case_id']}: no data in {'static table' if args.static_table else 'live API'}")
            continue

        ranked = rank_candidates(cands, cfg=cfg)
        names = [d.get("drug_name", "") for d in ranked]

        # STANDARD P@3 — denominator always 3, NOT min(3, |known|)
        p3_std = sum(1 for k in known if any(k.lower() in n.lower() or n.lower() in k.lower() for n in names[:3])) / 3.0
        h3_val = 1.0 if any(
            any(k.lower() in n.lower() or n.lower() in k.lower() for n in names[:3])
            for k in known
        ) else 0.0

        hard_p3_std.append(p3_std)
        hard_h3.append(h3_val)
        by_category.setdefault(cat, []).append(p3_std)

        status = "PASS" if h3_val else "FAIL"
        top3_names = names[:3]
        print(f"  [{status}] {case['case_id']}")
        print(f"         known: {known}")
        print(f"         top-3: {top3_names}")
        print(f"         P@3_std={p3_std:.3f}  Hit@3={h3_val:.0f}")

    print()
    print("── HARD BENCHMARK SUMMARY ────────────────────────────────")
    print(f"  Sensitivity cases evaluated:    {len(hard_p3_std)}")
    print(f"  Standard P@3 (denominator=3):   {avg(hard_p3_std):.3f}  (target ≥ 0.45)")
    print(f"  Hit@3:                           {avg(hard_h3):.1%}  (target ≥ 80%)")
    print(f"  False positives (negatives):     {hard_fp}  (target = 0)")
    print()
    print("  By category (std P@3):")
    for cat, vals in sorted(by_category.items()):
        print(f"    {cat:<22}: n={len(vals)}  P@3={avg(vals):.3f}")
    print()
    print("── INTERPRETATION ────────────────────────────────────────")
    print("  Standard P@3 CANNOT exceed 0.33 for single-drug cases even")
    print("  when the system ranks that drug #1.  For multi-drug cases")
    print("  (≥2 known drugs) it can reach 0.67 (2/3) or 1.0 (3+/3).")
    print("  A standard P@3 of 0.45 means the system retrieves roughly")
    print("  1-2 known drugs per 3 slots on average across hard cases.")
    print()

    hard_result = {
        "mode": "hard_clinical_benchmark",
        "api_source": api_mode,
        "cross_validation": {
            "baseline": cv_baseline,
            "tuned": cv_tuned,
            "holdout_80_20_tuned": holdout_tuned,
        },
        "total_hard_cases": len(HARD_CLINICAL_CASES),
        "sensitivity_evaluated": len(hard_p3_std),
        "standard_precision_at_3": round(avg(hard_p3_std), 4),
        "hit_at_3": round(avg(hard_h3), 4),
        "false_positives": hard_fp,
        "by_category": {cat: round(avg(vals), 4) for cat, vals in by_category.items()},
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hard_benchmark_results.json")
    with open(out_path, "w") as fh:
        json.dump(hard_result, fh, indent=2)
    print(f"Results written to hard_benchmark_results.json")
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════
# FULL BENCHMARK (default mode)
# ════════════════════════════════════════════════════════════════════════
api_mode = "static table" if args.static_table else "live API"
print(f"[API source: {api_mode}]")

# ── Sensitivity: does system find the right drug for cases with known drugs? ──
sens_p3: list[float] = []
sens_mrr: list[float] = []
sens_h3: list[float] = []
sens_missing: list[str] = []  # cases with no OncoKB data

for case in SENSITIVITY_CASES:
    if not case.get("known_drugs"):
        continue
    cands = build_candidates(
        case["gene"],
        case["variant"],
        case.get("cancer_type"),
        case.get("alphamissense_score"),
    )
    if not cands:
        sens_missing.append(case["case_id"])
        continue
    ranked = rank_candidates(cands, cfg=cfg)
    names = [d.get("drug_name", "") for d in ranked]
    known = case["known_drugs"]
    sens_p3.append(precision_at_k(names, known, 3))
    sens_mrr.append(mean_reciprocal_rank(names, known))
    sens_h3.append(1.0 if hit_at_k(names, known, 3) else 0.0)

# Per-difficulty breakdown
for difficulty in ("L1_L2", "L3_L4"):
    subset = [c for c in SENSITIVITY_CASES if c.get("difficulty") == difficulty and c.get("known_drugs")]
    p3_sub, h3_sub = [], []
    for case in subset:
        cands = build_candidates(
            case["gene"],
            case["variant"],
            case.get("cancer_type"),
            case.get("alphamissense_score"),
        )
        if not cands:
            continue
        ranked = rank_candidates(cands, cfg=cfg)
        names = [d.get("drug_name", "") for d in ranked]
        p3_sub.append(precision_at_k(names, case["known_drugs"], 3))
        h3_sub.append(1.0 if hit_at_k(names, case["known_drugs"], 3) else 0.0)
    print(f"  {difficulty}: n={len(p3_sub)}  P@3={avg(p3_sub):.3f}  Hit@3={avg(h3_sub):.1%}")

# ── Specificity: does system avoid hallucinating drugs for VUS/no-target cases? ─
fp_total = 0
fp_fail = 0
fp_failures: list[dict] = []

for case in VUS_NEGATIVE_CASES:
    fp_total += 1
    cands = build_candidates(
        case["gene"],
        case["variant"],
        case.get("cancer_type"),
        case.get("alphamissense_score"),
    )
    if not cands:
        continue    # no candidates produced → correct (pass)
    ranked = rank_candidates(cands, cfg=cfg)
    top3 = ranked[:3]
    # False positive = any drug in top-3 with a high rank_score (> 0.25) AND an OncoKB level
    high_conf = [
        d for d in top3
        if d.get("rank_score", 0) > 0.25 and d.get("oncokb_level") not in (None, "")
    ]
    if high_conf:
        fp_fail += 1
        fp_failures.append({
            "case_id": case["case_id"],
            "gene": case["gene"],
            "variant": case["variant"],
            "spurious_drugs": [d["drug_name"] for d in high_conf[:3]],
            "max_score": max(d.get("rank_score", 0) for d in high_conf),
        })

fp_rate = fp_fail / fp_total if fp_total > 0 else 0.0

# ── Level-1 only metrics ──────────────────────────────────────────────────────
l1_p3, l1_h3 = [], []
for case in LEVEL_1_CASES:
    if not case.get("known_drugs"):
        continue
    cands = build_candidates(
        case["gene"],
        case["variant"],
        case.get("cancer_type"),
        case.get("alphamissense_score"),
    )
    if not cands:
        continue
    ranked = rank_candidates(cands, cfg=cfg)
    names = [d.get("drug_name", "") for d in ranked]
    l1_p3.append(precision_at_k(names, case["known_drugs"], 3))
    l1_h3.append(1.0 if hit_at_k(names, case["known_drugs"], 3) else 0.0)

# ── Report ────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  OPENONCOLOGY OFFLINE BENCHMARK REPORT")
print("=" * 60)
print(f"\nTotal gold-standard cases: {len(GOLD_STANDARD_CASES)}")
print(f"  Sensitivity cases (known drug expected): {len(SENSITIVITY_CASES)}")
print(f"  Specificity cases (VUS/no-target, FP test): {len(VUS_NEGATIVE_CASES)}")
print(f"  Cases missing from OncoKB table (no data): {len(sens_missing)}")
print()
print("── SENSITIVITY (correct drug recall) ────────────────────")
print(f"  Cases with OncoKB data:  {len(sens_p3)}")
print(f"  P@3  (all sensitivity):  {avg(sens_p3):.3f}")
print(f"  Hit@3:                   {avg(sens_h3):.1%}")
print(f"  MRR:                     {avg(sens_mrr):.3f}")
print()
print("  Level-1 only:")
print(f"    P@3:   {avg(l1_p3):.3f}")
print(f"    Hit@3: {avg(l1_h3):.1%}")
print()
print("  By difficulty tier:")
for difficulty in ("L1_L2", "L3_L4"):
    subset = [c for c in SENSITIVITY_CASES if c.get("difficulty") == difficulty and c.get("known_drugs")]
    p3_sub, h3_sub = [], []
    for case in subset:
        cands = build_candidates(
            case["gene"],
            case["variant"],
            case.get("cancer_type"),
            case.get("alphamissense_score"),
        )
        if not cands:
            continue
        ranked = rank_candidates(cands, cfg=cfg)
        names = [d.get("drug_name", "") for d in ranked]
        p3_sub.append(precision_at_k(names, case["known_drugs"], 3))
        h3_sub.append(1.0 if hit_at_k(names, case["known_drugs"], 3) else 0.0)
    print(f"    {difficulty}: n={len(p3_sub)}  P@3={avg(p3_sub):.3f}  Hit@3={avg(h3_sub):.1%}")

print()
print("── SPECIFICITY (false positive rate on VUS/no-target) ────")
print(f"  VUS / no-target cases:   {fp_total}")
print(f"  Correctly returned empty: {fp_total - fp_fail}")
print(f"  False positives:          {fp_fail}")
print(f"  FP rate:                  {fp_rate:.1%}")
if fp_failures:
    print()
    print("  FALSE POSITIVE DETAILS:")
    for f in fp_failures:
        drugs_str = ", ".join(f["spurious_drugs"])
        print(f"    {f['case_id']}: {drugs_str}  (score={f['max_score']:.3f})")

print()
print("── IMPORTANT CAVEATS ─────────────────────────────────────")
print(f"  1. API source: {api_mode}.  Results depend on this choice.")
print("  2. P@3 METRIC NOTE:")
print("       Standard P@3 (denominator=3): reported as precision_at_3_standard")
print("       Normalised P@3 (denominator=min(3,|drugs|)): precision_at_3")
print("       Standard is the honest, comparable number. Normalised gives")
print("       credit to single-drug cases.  Report BOTH.")
print("  3. Sensitivity cases only test genes IN the data source.")
print(f"     {len(sens_missing)} cases had no entry and were excluded.")
print("  4. Clinical outcome correlation: NOT MEASURED.")
print("  5. Performance on co-mutated / low-VAF cases: NOT MEASURED offline.")
print("  6. Run with --hard-only for the Hard Clinical Benchmark (22 cases).")

# ── Machine-readable output ───────────────────────────────────────────────────
sens_p3_std = [
    sum(1 for k in case["known_drugs"] if any(
        k.lower() in n.lower() or n.lower() in k.lower()
        for n in [
            d.get("drug_name", "")
            for d in rank_candidates(
                build_candidates(
                    case["gene"],
                    case["variant"],
                    case.get("cancer_type"),
                    case.get("alphamissense_score"),
                ),
                cfg=cfg,
            )
        ][:3]
    )) / 3.0
    for case in SENSITIVITY_CASES
    if case.get("known_drugs") and build_candidates(
        case["gene"],
        case["variant"],
        case.get("cancer_type"),
        case.get("alphamissense_score"),
    )
]

result = {
    "run_mode": api_mode,
    "cross_validation": {
        "baseline": cv_baseline,
        "tuned": cv_tuned,
        "holdout_80_20_tuned": holdout_tuned,
    },
    "total_cases": len(GOLD_STANDARD_CASES),
    "sensitivity_cases": len(SENSITIVITY_CASES),
    "sensitivity_with_data": len(sens_p3),
    "sensitivity_missing_data": len(sens_missing),
    "precision_at_3": round(avg(sens_p3), 4),
    "precision_at_3_note": "normalised denominator = min(3, |known_drugs|)",
    "precision_at_3_standard": round(avg(sens_p3_std), 4),
    "precision_at_3_standard_note": "denominator = 3 (comparable to published benchmarks)",
    "hit_at_3": round(avg(sens_h3), 4),
    "mrr": round(avg(sens_mrr), 4),
    "level_1_precision_at_3": round(avg(l1_p3), 4),
    "level_1_hit_at_3": round(avg(l1_h3), 4),
    "specificity_cases": fp_total,
    "false_positive_count": fp_fail,
    "false_positive_rate": round(fp_rate, 4),
    "fp_failures": fp_failures,
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmark_results.json")
with open(out_path, "w") as fh:
    json.dump(result, fh, indent=2)
print(f"\nResults written to benchmark_results.json")
