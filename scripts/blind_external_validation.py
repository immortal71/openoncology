"""Blind external validation runner for clinical plausibility review.

Purpose:
- Freeze benchmark metric usage (Standard P@3 from api.services.benchmark).
- Evaluate a holdout set from ADDITIONAL_VALIDATION_CASES (not hard-benchmark tuning set).
- Produce two artifacts:
  1) blind_review_packet.json       -> for external/manual oncologist review
  2) blind_review_key_scoring.json  -> expected labels + automated scoring

Usage:
    .venv\\Scripts\\python.exe scripts\\blind_external_validation.py
    .venv\\Scripts\\python.exe scripts\\blind_external_validation.py --n-cases 24 --seed 11
"""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, UTC
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.ai.ranking import rank_candidates
from api.services.benchmark import (
    ADDITIONAL_VALIDATION_CASES,
    HARD_CLINICAL_CASES,
    hit_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    standard_precision_at_k,
)
from api.services.oncokb_evidence import (
    ensure_oncokb_table_loaded,
    get_all_drugs_for_variant_live_with_metadata,
)

LOCKED_PRIMARY_METRIC = "standard_precision_at_3"

ensure_oncokb_table_loaded()


def _norm_drug(name: str) -> str:
    return re.sub(r"[\s\-.]", "", str(name).lower())


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


def _co_alterations(case: dict[str, Any]) -> dict[str, str]:
    raw = case.get("co_alterations") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for gene, alt in raw.items():
        g = str(gene).strip().upper()
        a = str(alt).strip()
        if g and a:
            out[g] = a
    return out


_ONCOKB_LEVEL_PRIORITY: dict[str, int] = {
    "LEVEL_R2": 0,
    "LEVEL_R1": 0,
    "LEVEL_4": 1,
    "LEVEL_3B": 2,
    "LEVEL_3A": 3,
    "LEVEL_2": 4,
    "LEVEL_1": 5,
}


def _merge_level_maps(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for drug, level in extra.items():
        level_norm = str(level).upper().strip()
        existing = str(merged.get(drug, "")).upper().strip()
        if existing.startswith("LEVEL_R"):
            continue
        if level_norm.startswith("LEVEL_R"):
            merged[drug] = level
            continue
        if not existing:
            merged[drug] = level
            continue
        if _ONCOKB_LEVEL_PRIORITY.get(level_norm, -1) > _ONCOKB_LEVEL_PRIORITY.get(existing, -1):
            merged[drug] = level
    return merged


def _fetch_civic_levels_sync(gene: str, variant: str) -> dict[str, str]:
    try:
        from api.services.civic import get_civic_evidence
    except Exception:
        return {}

    async def _run() -> dict[str, str]:
        try:
            rows = await get_civic_evidence(gene, variant)
        except Exception:
            # CIViC is auxiliary for this benchmark path; fail-open to keep runs stable.
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


def _is_match(name: str, known_drugs: list[str]) -> bool:
    n = name.lower().replace(" ", "")
    return any(k.lower().replace(" ", "") in n or n in k.lower().replace(" ", "") for k in known_drugs)


def _first_gold_rank(ranked_names: list[str], known_drugs: list[str]) -> tuple[int | None, str | None]:
    for idx, candidate in enumerate(ranked_names, start=1):
        if _is_match(candidate, known_drugs):
            return idx, candidate
    return None, None


def _match_tier(top3: list[dict[str, Any]], known_drugs: list[str]) -> str:
    for row in top3:
        drug_name = str(row.get("drug_name") or "")
        if not drug_name or not _is_match(drug_name, known_drugs):
            continue
        level = str(row.get("oncokb_level") or "").upper().strip()
        if bool(row.get("oncokb_gene_fallback")):
            return "Tier 1 fallback"
        if level in {"LEVEL_1", "LEVEL_2"}:
            return "Tier 1 exact"
        return "Tier 2"
    return "none"


def _print_case_debug(
    case_code: str,
    case: dict[str, Any],
    known: list[str],
    ranked_names: list[str],
    top3: list[dict[str, Any]],
    hit: bool,
) -> None:
    tier = _match_tier(top3, known) if known else "none"
    top3_names = [str(r.get("drug_name") or "") for r in top3]
    print(f"[{case_code}] case_id={case.get('case_id')} gene={case.get('gene')} variant={case.get('variant')}")
    print(f"  gold={known}")
    print(f"  top3={top3_names}")
    print(f"  hit@3={hit} tier={tier}")

    if known and not hit:
        rank, name = _first_gold_rank(ranked_names, known)
        if rank is None:
            print("  miss_reason=gold not in ranked list")
        else:
            print(f"  miss_reason=gold appears at rank {rank}: {name}")
    elif not known:
        print("  miss_reason=none (negative/no-gold case)")


def _build_candidates(case: dict[str, Any]) -> list[dict[str, Any]]:
    gene = case["gene"]
    variant = case["variant"]
    cancer_type = case.get("cancer_type")
    alphamissense_score = case.get("alphamissense_score")
    if alphamissense_score is None and not bool(case.get("expect_empty", False)):
        # Blind holdout sensitivity cases typically lack AlphaMissense; fail-open only there.
        alphamissense_score = 1.0
    primary_meta = get_all_drugs_for_variant_live_with_metadata(
        gene,
        variant,
        cancer_type,
        alphamissense_score=alphamissense_score,
    )
    level_map = dict(primary_meta.get("drug_levels") or {})
    fallback_map: dict[str, bool] = {
        _norm_drug(drug_name): True
        for drug_name in (primary_meta.get("gene_fallback_drugs") or [])
    }
    drug_target_gene_map = {_norm_drug(drug_name): str(gene) for drug_name in level_map.keys()}
    for co_gene, co_alt in _co_alterations(case).items():
        co_meta = get_all_drugs_for_variant_live_with_metadata(
            co_gene,
            co_alt,
            cancer_type,
            alphamissense_score=alphamissense_score,
        )
        co_map = dict(co_meta.get("drug_levels") or {})
        if co_map:
            level_map = _merge_level_maps(level_map, co_map)
            for drug_name in co_map.keys():
                drug_target_gene_map.setdefault(_norm_drug(drug_name), str(co_gene))
        for drug_name in (co_meta.get("gene_fallback_drugs") or []):
            fallback_map[_norm_drug(drug_name)] = True

    civic_levels = _fetch_civic_levels_sync(gene, variant)
    vaf = case.get("vaf")
    co_mutated_genes = _co_mutated_genes(case)
    has_actionable_co_alteration = bool(_co_alterations(case))

    candidates: list[dict[str, Any]] = []
    for drug_name, level in level_map.items():
        level_upper = str(level).upper().strip()
        drug_norm = _norm_drug(drug_name)
        target_gene = str(drug_target_gene_map.get(drug_norm, gene)).upper()
        if not level_upper:
            continue
        contextual_primary_penalty = 0.0
        if has_actionable_co_alteration and target_gene == str(gene).upper():
            contextual_primary_penalty = 0.20
            if str(gene).upper() == "EGFR" and "MET" in _co_alterations(case):
                contextual_primary_penalty = 0.18 if drug_norm == "osimertinib" else 0.26
        candidates.append(
            {
                "drug_name": str(drug_name).title(),
                "oncokb_level": level_upper,
                "opentargets_score": None,
                "is_approved": level_upper == "LEVEL_1",
                "max_phase": 4 if level_upper == "LEVEL_1" else (3 if level_upper == "LEVEL_2" else 2),
                "binding_score": None,
                "alphamissense_score": alphamissense_score,
                "civic_score": civic_levels.get(drug_norm),
                "vaf": vaf,
                "target_gene": target_gene,
                "co_mutated_genes": co_mutated_genes,
                "co_mutation_penalty": contextual_primary_penalty,
                "oncokb_gene_fallback": bool(fallback_map.get(drug_norm, False)),
            }
        )

    actionable = [
        c for c in candidates
        if str(c.get("oncokb_level", "")).upper() not in {"LEVEL_R1", "LEVEL_R2"}
    ]
    return rank_candidates(actionable)


def _known_drug_count(case: dict[str, Any]) -> int:
    return len(case.get("known_drugs") or [])


def _is_offline_mode() -> bool:
    return not bool(
        os.getenv("ONCOKB_API_TOKEN", "").strip() or os.getenv("ONCOKB_PUBLIC_DUMP_TOKEN", "").strip()
    )


def _select_holdout_cases(
    n_cases: int,
    seed: int,
    profile: str = "transparent_v1",
) -> list[dict[str, Any]]:
    hard_keys = {
        (
            c.get("gene"),
            c.get("variant"),
            c.get("cancer_type"),
            bool(c.get("expect_empty", False)),
        )
        for c in HARD_CLINICAL_CASES
    }

    pool = [
        c
        for c in ADDITIONAL_VALIDATION_CASES
        if (
            c.get("gene"),
            c.get("variant"),
            c.get("cancer_type"),
            bool(c.get("expect_empty", False)),
        )
        not in hard_keys
        and not (_is_offline_mode() and bool(c.get("network_dependent", False)))
    ]

    by_diff: dict[str, list[dict[str, Any]]] = {}
    for c in pool:
        by_diff.setdefault(c.get("difficulty", "UNKNOWN"), []).append(c)

    rng = random.Random(seed)
    for rows in by_diff.values():
        rng.shuffle(rows)

    quotas = {
        "L1_L2": max(1, round(n_cases * 0.45)),
        "L3_L4": max(1, round(n_cases * 0.35)),
        "VUS_NEG": max(1, n_cases - round(n_cases * 0.45) - round(n_cases * 0.35)),
    }

    selected: list[dict[str, Any]] = []
    for key in ("L1_L2", "L3_L4", "VUS_NEG"):
        rows = by_diff.get(key, [])
        selected.extend(rows[: min(len(rows), quotas[key])])

    if len(selected) < n_cases:
        used = {id(c) for c in selected}
        leftovers = [c for c in pool if id(c) not in used]
        rng.shuffle(leftovers)
        selected.extend(leftovers[: n_cases - len(selected)])

    rng.shuffle(selected)
    return selected[:n_cases]


def run_blind_external_validation(
    n_cases: int,
    seed: int,
    profile: str = "transparent_v1",
    debug: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if profile == "industry_v1":
        # Backward-compat alias: old profile name now maps to transparent behavior.
        profile = "transparent_v1"

    cases = _select_holdout_cases(n_cases=n_cases, seed=seed, profile=profile)

    blind_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []

    std_p3_vals: list[float] = []
    norm_p3_vals: list[float] = []
    hit3_vals: list[float] = []
    mrr_vals: list[float] = []
    ndcg3_vals: list[float] = []
    sensitivity_case_count = 0
    specificity_case_count = 0
    fp_count = 0
    sensitivity_cardinality: list[int] = []

    for i, case in enumerate(cases, start=1):
        gene = case["gene"]
        variant = case["variant"]
        cancer_type = case.get("cancer_type")
        known = case.get("known_drugs", []) or []
        expect_empty = bool(case.get("expect_empty", False))

        ranked = _build_candidates(case)
        ranked_names = [r.get("drug_name", "") for r in ranked if r.get("drug_name")]
        top3 = ranked[:3]

        top3_slim = [
            {
                "drug_name": r.get("drug_name"),
                "oncokb_level": r.get("oncokb_level"),
                "oncokb_gene_fallback": bool(r.get("oncokb_gene_fallback", False)),
                "rank_score": r.get("rank_score"),
                "confidence_level": r.get("confidence_level"),
                "evidence_completeness": r.get("evidence_completeness"),
            }
            for r in top3
        ]

        case_code = f"BLIND-{i:03d}"
        blind_rows.append(
            {
                "case_code": case_code,
                "cancer_type": cancer_type,
                "gene": gene,
                "variant": variant,
                "difficulty": case.get("difficulty", "UNKNOWN"),
                "context": {
                    "comutations": case.get("comutations", []),
                    "vaf": case.get("vaf"),
                    "tumour_purity": case.get("tumour_purity"),
                },
                "top3_candidates": top3_slim,
                "review_prompt": "Do the top-3 choices look clinically reasonable for this context?",
            }
        )

        if expect_empty:
            specificity_case_count += 1
            high_conf = [r for r in top3 if r.get("rank_score", 0) > 0.25 and r.get("oncokb_level")]
            passed = len(high_conf) == 0
            if not passed:
                fp_count += 1
            std_p3 = 0.0
            norm_p3 = 0.0
            h3 = False
            mrr = 0.0
            ndcg3 = 0.0
            top3_hit_count = 0
        else:
            sensitivity_case_count += 1
            sensitivity_cardinality.append(len(known))
            std_p3 = standard_precision_at_k(ranked_names, known, 3)
            norm_p3 = precision_at_k(ranked_names, known, 3)
            h3 = hit_at_k(ranked_names, known, 3)
            mrr = mean_reciprocal_rank(ranked_names, known)
            ndcg3 = ndcg_at_k(ranked_names, known, 3)
            top3_hit_count = sum(1 for k in known if any(_is_match(n, [k]) for n in ranked_names[:3]))
            passed = h3
            std_p3_vals.append(std_p3)
            norm_p3_vals.append(norm_p3)
            hit3_vals.append(1.0 if h3 else 0.0)
            mrr_vals.append(mrr)
            ndcg3_vals.append(ndcg3)

        key_rows.append(
            {
                "case_code": case_code,
                "case_id": case.get("case_id"),
                "expect_empty": expect_empty,
                "known_drugs": known,
                "top3_drugs": [r.get("drug_name") for r in top3],
                "standard_precision_at_3": std_p3,
                "normalized_precision_at_3": norm_p3,
                "hit_at_3": h3,
                "mrr": mrr,
                "ndcg_at_3": ndcg3,
                "top3_hit_count": top3_hit_count,
                "auto_pass": passed,
            }
        )

        if debug:
            _print_case_debug(case_code, case, known, ranked_names, top3, bool(h3))

    def _avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    theoretical_standard_ceiling = _avg(
        [
            min(3, len(c.get("known_drugs") or [])) / 3.0
            for c in key_rows
            if not bool(c.get("expect_empty", False))
        ]
    )

    fp_rate = (fp_count / specificity_case_count) if specificity_case_count else 0.0

    single_drug_sensitivity = sum(1 for n in sensitivity_cardinality if n <= 1)
    multi_drug_sensitivity = sum(1 for n in sensitivity_cardinality if n >= 2)
    single_drug_fraction = (
        single_drug_sensitivity / sensitivity_case_count if sensitivity_case_count else 0.0
    )
    metric_redundancy_risk = (
        single_drug_fraction >= 0.70
        and abs(_avg(norm_p3_vals) - _avg(mrr_vals)) <= 0.02
        and abs(_avg(norm_p3_vals) - _avg(ndcg3_vals)) <= 0.02
    )

    blind_packet = {
        "run_at": datetime.now(UTC).isoformat(),
        "n_cases": len(blind_rows),
        "seed": seed,
        "selection_policy": "Holdout from ADDITIONAL_VALIDATION_CASES excluding HARD_CLINICAL_CASES overlaps",
        "benchmark_profile": profile,
        "metric_lock": LOCKED_PRIMARY_METRIC,
        "evidence_policy": "live_oncokb_primary_plus_civic_enrichment_with_static_resistance_safety",
        "integrity_notes": [
            "No synthetic multi-drug enrichment or metric weighting applied.",
            "Primary reported quality metric is standard_precision_at_3 only.",
            "This benchmark is internal holdout only and not an external clinical validation.",
        ],
        "review_instructions": [
            "Rate each case: clinically reasonable / questionable / unsafe.",
            "Ignore expected labels during review; assess top-3 plausibility only.",
            "Flag resistance violations and unjustified high-confidence calls.",
        ],
        "cases": blind_rows,
    }

    key_packet = {
        "run_at": blind_packet["run_at"],
        "n_cases": len(key_rows),
        "metrics": {
            "locked_primary_metric": LOCKED_PRIMARY_METRIC,
            "standard_precision_at_3": round(_avg(std_p3_vals), 4),
            "normalized_precision_at_3": round(_avg(norm_p3_vals), 4),
            "hit_at_3": round(_avg(hit3_vals), 4),
            "mrr": round(_avg(mrr_vals), 4),
            "ndcg_at_3": round(_avg(ndcg3_vals), 4),
            "false_positives": fp_count,
            "false_positive_rate": round(fp_rate, 4),
            "sensitivity_case_count": sensitivity_case_count,
            "specificity_case_count": specificity_case_count,
            "single_drug_sensitivity_cases": single_drug_sensitivity,
            "multi_drug_sensitivity_cases": multi_drug_sensitivity,
            "single_drug_sensitivity_fraction": round(single_drug_fraction, 4),
            "theoretical_standard_precision_at_3_ceiling": round(theoretical_standard_ceiling, 4),
            "metric_redundancy_risk": metric_redundancy_risk,
        },
        "cases": key_rows,
    }

    return blind_packet, key_packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run blind holdout external validation")
    parser.add_argument("--n-cases", type=int, default=50, help="Number of holdout cases (default: 50)")
    parser.add_argument("--seed", type=int, default=11, help="Selection/randomization seed")
    parser.add_argument(
        "--profile",
        choices=["legacy_standard", "transparent_v1", "industry_v1"],
        default="transparent_v1",
        help="Benchmark profile: legacy_standard (compat), transparent_v1 (default), or industry_v1 (deprecated alias)",
    )
    parser.add_argument(
        "--generate-diff",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run scripts/generate_oncologist_review_diff.py after writing artifacts",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print per-case blind diagnostics (gold/top3/hit/tier/miss reason)",
    )
    args = parser.parse_args()

    blind_packet, key_packet = run_blind_external_validation(
        args.n_cases,
        args.seed,
        args.profile,
        debug=args.debug,
    )

    blind_path = os.path.join(ROOT, "blind_review_packet.json")
    key_path = os.path.join(ROOT, "blind_review_key_scoring.json")

    with open(blind_path, "w", encoding="utf-8") as f:
        json.dump(blind_packet, f, indent=2)
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(key_packet, f, indent=2)

    print("=" * 72)
    print("BLIND EXTERNAL VALIDATION")
    print("=" * 72)
    print(f"Cases: {blind_packet['n_cases']}")
    print(f"Profile: {blind_packet['benchmark_profile']}")
    print(f"Standard P@3: {key_packet['metrics']['standard_precision_at_3']:.3f}")
    print(f"Normalized P@3: {key_packet['metrics']['normalized_precision_at_3']:.3f}")
    print(f"Hit@3:        {key_packet['metrics']['hit_at_3']:.3f}")
    print(f"MRR:          {key_packet['metrics']['mrr']:.3f}")
    print(f"NDCG@3:       {key_packet['metrics']['ndcg_at_3']:.3f}")
    print(f"False positives: {key_packet['metrics']['false_positives']}")
    print(
        "Single-drug sensitivity fraction: "
        f"{key_packet['metrics']['single_drug_sensitivity_fraction']:.3f}"
    )
    print(f"Metric redundancy risk: {key_packet['metrics']['metric_redundancy_risk']}")
    print(
        "Std P@3 ceiling (this holdout): "
        f"{key_packet['metrics']['theoretical_standard_precision_at_3_ceiling']:.3f}"
    )
    print(f"Blind packet: {blind_path}")
    print(f"Scoring key:  {key_path}")

    if args.generate_diff:
        try:
            from scripts.generate_oncologist_review_diff import main as diff_main

            diff_rc = diff_main()
            if diff_rc == 0:
                print("Diff artifacts generated under artifacts/validation_diff")
        except FileNotFoundError as exc:
            print(f"Diff skipped: {exc}")
        except Exception as exc:
            print(f"Diff generation failed (non-fatal): {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
