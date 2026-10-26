"""Score a MSK-CHORD cohort against a mutation-ranker's output (OO-29).

Two numbers, kept apart:

  1. ground_truth_matched: of the patients in the cohort, how many have an
     alteration that justifies the targeted drug they received, according to
     the FDA-label-based map in targeted_drug_targets.TARGETS. This measures
     the cohort, not the ranker, and sets the ceiling.

  2. ranker_hit: of the patients the ranker was run on, how many had the
     received drug in its top 3 for the alteration we identified. Needs a
     results file with pipeline_top3 per patient.

Fusion-only expectations are reported separately as UNEVALUABLE instead of
being counted as misses, since MSK-CHORD's SV endpoint is not exposed in the
fetch script yet.

Usage:
    python scripts/mskchord/score_mskchord.py validation_results/msk_chord_targeted_cohort.json
    python scripts/mskchord/score_mskchord.py cohort.json --results run.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from targeted_drug_targets import targeted_match

try:
    from services.oncology_atc import parent_name as _parent_name
except ImportError:
    def _parent_name(x: str) -> str:
        return (x or "").strip().lower()


def _norm(name: str) -> str:
    return _parent_name(name)


def _normalize_alt(alt: dict) -> dict:
    """The Chrome prototype and the Python fetcher use different field names;
    accept either, so a cohort file produced by either one scores the same."""
    return {
        "gene": alt.get("gene") or alt.get("g") or "",
        "protein_change": alt.get("protein_change") or alt.get("a") or "",
        "mutation_type": alt.get("mutation_type") or alt.get("t") or "",
        "alteration": alt.get("alteration") or alt.get("alt") or "",
    }


def _label(record: dict) -> dict:
    """For each targeted drug the patient received, classify its match."""
    muts = [_normalize_alt(m) for m in (record.get("mutations") or [])]
    cnas = [_normalize_alt(c) for c in (record.get("cnas") or [])]
    per_drug = []
    for drug in record.get("targeted_drugs") or []:
        verdict, reasons = targeted_match(drug, muts, cnas)
        per_drug.append({"drug": drug, "verdict": verdict, "reasons": reasons})
    # One patient-level verdict: hit > unevaluable > miss > unknown_drug.
    rank = {"hit": 0, "unevaluable": 1, "miss": 2, "unknown_drug": 3}
    best = min(per_drug, key=lambda x: rank[x["verdict"]]) if per_drug else {"verdict": "no_drugs"}
    return {"per_drug": per_drug, "verdict": best["verdict"]}


def ground_truth(records: list[dict]) -> dict:
    labels = [_label(r) for r in records]
    tally = collections.Counter(x["verdict"] for x in labels)
    by_cancer = collections.defaultdict(collections.Counter)
    for r, lab in zip(records, labels):
        by_cancer[r.get("cancer_type") or "Unknown"][lab["verdict"]] += 1
    return {
        "total_patients": len(records),
        "verdicts": dict(tally),
        "benchmarkable_hits": tally["hit"],
        "ceiling": tally["hit"] + tally["unevaluable"],
        "by_cancer": {k: dict(v) for k, v in by_cancer.items()},
    }


def _received_drugs(record: dict) -> set[str]:
    return {_norm(d) for d in record.get("targeted_drugs") or []}


def _top3(record: dict) -> list[str]:
    return [_norm(d) for d in (record.get("pipeline_top3") or [])]


def ranker_score(records: list[dict], results: list[dict]) -> dict:
    by_pid = {r["patient_id"]: r for r in results}
    hits = 0
    with_pred = 0
    missed = []
    for rec in records:
        verdict = _label(rec)["verdict"]
        if verdict != "hit":
            continue  # not benchmarkable
        res = by_pid.get(rec["patient_id"])
        if not res or not res.get("pipeline_top3"):
            continue
        with_pred += 1
        got = _received_drugs(rec)
        top3 = _top3(res)
        if any(d in got for d in top3):
            hits += 1
        else:
            missed.append({"patient_id": rec["patient_id"], "top3": res.get("pipeline_top3"),
                           "received": sorted(rec.get("targeted_drugs") or [])})
    return {
        "benchmarkable_patients": sum(1 for r in records if _label(r)["verdict"] == "hit"),
        "ran_on": with_pred,
        "top3_hits": hits,
        "miss_examples": missed[:10],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cohort")
    p.add_argument("--results", help="A pipeline results file in the same shape as "
                                     "scripts/concordance_pilot_run_pipeline.py produces.")
    args = p.parse_args()
    with open(args.cohort) as fh:
        records = json.load(fh)
    gt = ground_truth(records)
    print(f"Cohort: {gt['total_patients']} patients")
    print(f"  benchmarkable (alteration matches the drug under its label): {gt['benchmarkable_hits']}")
    uneval = gt['verdicts'].get('unevaluable', 0)
    miss = gt['verdicts'].get('miss', 0)
    unk = gt['verdicts'].get('unknown_drug', 0)
    print(f"  unevaluable (fusion-only; SV endpoint not pulled): {uneval}")
    print(f"  no qualifying alteration for any received drug: {miss}")
    print(f"  unknown drug in the targeted map: {unk}")
    print("  by cancer type:")
    for c, v in sorted(gt["by_cancer"].items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        total = sum(v.values())
        print(f"    {c}: {total} ({'hit':>4} {v.get('hit', 0)}, "
              f"{'miss':>4} {v.get('miss', 0)}, {'uneval':>6} {v.get('unevaluable', 0)})")

    if args.results:
        with open(args.results) as fh:
            results = json.load(fh)
        rs = ranker_score(records, results)
        print()
        print(f"Ranker: ran on {rs['ran_on']} of {rs['benchmarkable_patients']} benchmarkable patients")
        pct = f"{100 * rs['top3_hits'] / rs['ran_on']:.1f}%" if rs['ran_on'] else "n/a"
        print(f"  top-3 hits: {rs['top3_hits']} ({pct})")
        if rs['miss_examples']:
            print("  example misses:")
            for m in rs['miss_examples'][:5]:
                print(f"    {m['patient_id']}: top3={m['top3']} received={m['received']}")


if __name__ == "__main__":
    main()
