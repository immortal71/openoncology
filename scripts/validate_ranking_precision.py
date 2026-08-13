"""Analytical validation gate: drug ranking Precision@K against the gold cases.

WHAT THIS MEASURES, AND WHAT IT CANNOT
--------------------------------------
docs/REGULATORY_FRAMEWORK.md section 3.1 lists "Drug ranking Precision@3 vs.
OncoKB L1/L2, target >= 0.60" as a validation gate. This script measures it
against GOLD_STANDARD_CASES in api/services/benchmark.py.

Before quoting the number, read the leakage section it prints.

The gold cases and the pipeline's evidence table are both derived from OncoKB.
Measured on 2026-08-13, 94.5% of gold cases have their expected drugs fully
contained in the answer the evidence table already returns for the same variant
(155 cases where the gold set is exactly the table's answer, 260 where it is a
subset, out of 439 with any table answer). For those cases Precision@3 is not
asking "is this the right drug", it is asking "can the ranker put drugs it
already holds into the top three". That is a real and useful question about
ranking, and it is not a question about accuracy.

This is a milder version of the defect that made the oncologist-concordance
benchmark return 100%. It is milder because the gold cases carry OncoKB level
citations rather than being computed from the drug, and because a minority of
cases genuinely disagree with the table. But the direction of the bias is the
same, so the script reports three numbers rather than one:

  overall          the gate figure, on every gold case
  contained        cases whose gold drugs the table already holds (leaky)
  independent      cases whose gold drugs the table does NOT fully hold

The independent subset is small, and it is the only one that carries any signal
about whether the evidence table is right. It is reported with its denominator
so nobody mistakes it for a robust estimate.

Usage:
    python scripts/validate_ranking_precision.py
    python scripts/validate_ranking_precision.py --k 3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "ranking-precision-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

_RESULTS_OUT = os.path.join(_REPO_ROOT, "validation_results", "ranking_precision.json")

TARGET_PRECISION_AT_3 = 0.60


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _rank_for(gene: str, variant: str) -> tuple[list[str], set[str]]:
    """Top-ranked drug names and the raw table answer, via the production path."""
    from ai.ranking import rank_candidates
    from services.oncokb_evidence import get_all_drugs_for_variant

    evidence = get_all_drugs_for_variant(gene, variant, alphamissense_score=1.0) or {}
    table_drugs = {_norm(d) for d in evidence}

    candidates = []
    for drug_name, level in evidence.items():
        level_text = str(level)
        if "R" in level_text:  # resistance markers are not recommendations
            continue
        candidates.append({
            "drug_name": drug_name,
            "oncokb_level": level,
            "is_approved": True,
            "max_phase": 4,
            "opentargets_score": 0.8 if "LEVEL_1" in level_text else (
                0.6 if "LEVEL_2" in level_text else 0.4),
        })
    if not candidates:
        return [], table_drugs
    return [c["drug_name"] for c in rank_candidates(candidates)], table_drugs


def _precision_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    top = ranked[:k]
    if not top:
        return 0.0
    return sum(1 for d in top if _norm(d) in gold) / len(top)


def _reciprocal_rank(ranked: list[str], gold: set[str]) -> float:
    for i, drug in enumerate(ranked, 1):
        if _norm(drug) in gold:
            return 1.0 / i
    return 0.0


def _summarise(rows: list[dict], k: int) -> dict:
    if not rows:
        return {"n": 0}
    scored = [r for r in rows if r["ranked"]]
    n = len(rows)
    n_scored = len(scored)
    return {
        "n_cases": n,
        "n_with_a_ranking": n_scored,
        "n_no_prediction": n - n_scored,
        "precision_at_1": round(sum(r["p_at_1"] for r in scored) / n_scored, 4) if n_scored else 0.0,
        f"precision_at_{k}": round(sum(r["p_at_k"] for r in scored) / n_scored, 4) if n_scored else 0.0,
        "precision_at_5": round(sum(r["p_at_5"] for r in scored) / n_scored, 4) if n_scored else 0.0,
        "hit_at_1": round(sum(1 for r in scored if r["p_at_1"] > 0) / n_scored, 4) if n_scored else 0.0,
        "mrr": round(sum(r["rr"] for r in scored) / n_scored, 4) if n_scored else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    k = args.k

    from services.benchmark import GOLD_STANDARD_CASES

    rows: list[dict] = []
    for case in GOLD_STANDARD_CASES:
        gold = {_norm(d) for d in (case.get("known_drugs") or []) if d}
        if not gold:
            continue
        gene = case.get("gene")
        variant = case.get("variant")
        if not gene or not variant:
            continue

        ranked, table_drugs = _rank_for(gene, variant)

        # Leakage classification: does the table already hold every gold drug?
        if not table_drugs:
            containment = "no_table_answer"
        elif gold <= table_drugs:
            containment = "contained"
        elif gold & table_drugs:
            containment = "partial"
        else:
            containment = "independent"

        rows.append({
            "case_id": case.get("case_id"),
            "gene": gene,
            "variant": variant,
            "cancer_type": case.get("cancer_type"),
            "oncokb_level": case.get("oncokb_level"),
            "known_drugs": case.get("known_drugs"),
            "ranked_top5": ranked[:5],
            "ranked": bool(ranked),
            "containment": containment,
            "p_at_1": _precision_at_k(ranked, gold, 1),
            "p_at_k": _precision_at_k(ranked, gold, k),
            "p_at_5": _precision_at_k(ranked, gold, 5),
            "rr": _reciprocal_rank(ranked, gold),
        })

    overall = _summarise(rows, k)
    contained = _summarise([r for r in rows if r["containment"] == "contained"], k)
    independent = _summarise(
        [r for r in rows if r["containment"] in ("independent", "partial")], k
    )

    by_containment = {}
    for label in ("contained", "partial", "independent", "no_table_answer"):
        by_containment[label] = sum(1 for r in rows if r["containment"] == label)

    n_judgeable = sum(v for key, v in by_containment.items() if key != "no_table_answer")
    leak_pct = (
        100.0 * by_containment["contained"] / n_judgeable if n_judgeable else 0.0
    )

    headline = overall.get(f"precision_at_{k}", 0.0)
    passed = headline >= TARGET_PRECISION_AT_3 and k == 3

    print("=" * 74)
    print(f"DRUG RANKING PRECISION@{k}  (gold cases in api/services/benchmark.py)")
    print("=" * 74)
    print(f"  gold cases with drugs        : {len(rows)}")
    print(f"  produced a ranking           : {overall['n_with_a_ranking']}")
    print(f"  no prediction                : {overall['n_no_prediction']}")
    print()
    print(f"  Precision@1                  : {overall['precision_at_1']}")
    print(f"  Precision@{k}                  : {headline}")
    print(f"  Precision@5                  : {overall['precision_at_5']}")
    print(f"  Hit@1                        : {overall['hit_at_1']}")
    print(f"  MRR                          : {overall['mrr']}")
    print()
    print("-" * 74)
    print("  LEAKAGE: how much of this is the table grading itself")
    print("-" * 74)
    print(f"  gold drugs already in the table (contained) : {by_containment['contained']}")
    print(f"  partial overlap                             : {by_containment['partial']}")
    print(f"  gold drugs NOT in the table (independent)   : {by_containment['independent']}")
    print(f"  no table answer at all                      : {by_containment['no_table_answer']}")
    print(f"  => {leak_pct:.1f}% of judgeable cases are self-graded")
    print()
    print(f"  Precision@{k} on the contained (leaky) subset  : "
          f"{contained.get(f'precision_at_{k}')}  (n={contained.get('n_cases', 0)})")
    print(f"  Precision@{k} on the independent subset       : "
          f"{independent.get(f'precision_at_{k}')}  (n={independent.get('n_cases', 0)})")
    print()
    print("=" * 74)
    print(f"  GATE (REGULATORY_FRAMEWORK.md 3.1): Precision@3 >= {TARGET_PRECISION_AT_3}")
    print(f"  RESULT: {headline}  ->  {'PASS' if passed else 'FAIL'}")
    print()
    print("  This gate measures RANKING, not accuracy. Most gold cases have")
    print("  their expected drugs already in the evidence table being graded,")
    print("  so a high figure says the ranker orders its own table well. It")
    print("  does not say the table is right. For that, see")
    print("  docs/BENCHMARK_NCI_MATCH.md, and note the limitation stated there.")
    print("=" * 74)

    payload = {
        "gate": "drug_ranking_precision_at_3",
        "target": {"metric": f"precision_at_{k}", "threshold": TARGET_PRECISION_AT_3},
        "result": {f"precision_at_{k}": headline, "passed": bool(passed)},
        "what_this_measures": (
            "Ranking quality over the pipeline's own evidence table. "
            f"{leak_pct:.1f}% of judgeable gold cases have their expected drugs already "
            "contained in that table, so this is largely a self-consistency check and "
            "cannot support a claim about evidence correctness."
        ),
        "metrics_overall": overall,
        "metrics_contained_subset": contained,
        "metrics_independent_subset": independent,
        "containment_counts": by_containment,
        "self_graded_pct": round(leak_pct, 2),
        "cases": rows,
    }
    os.makedirs(os.path.dirname(_RESULTS_OUT), exist_ok=True)
    with open(_RESULTS_OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {os.path.relpath(_RESULTS_OUT, _REPO_ROOT)}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
