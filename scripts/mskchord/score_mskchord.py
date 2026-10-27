"""Score a MSK-CHORD cohort against a mutation-ranker's output (OO-29).

Two numbers, kept apart:

  1. ground_truth_matched: of the patients in the cohort, how many have an
     alteration that justifies the targeted drug they received, according to
     the FDA-label-based map in targeted_drug_targets.TARGETS. This measures
     the cohort, not the ranker, and sets the ceiling.

  2. ranker_hit: of the patients the ranker was run on, how many had the
     received drug in its top 3 for the alteration we identified. Needs a
     results file with pipeline_top3 per patient.

Fusion expectations are resolved against the per-patient fusion list pulled
from MSK-CHORD's structural-variant endpoint; a drug whose fusion rule has
no matching fusion counts as a miss.

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
    fusions = record.get("fusions") or []
    per_drug = []
    for drug in record.get("targeted_drugs") or []:
        verdict, reasons = targeted_match(drug, muts, cnas, fusions)
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


# Drug classes with equivalent molecular target. A patient whose record shows
# erlotinib while the ranker returns afatinib or osimertinib has the same
# treatment decision; the ranker did not pick the wrong class, it picked a
# different drug in the same class. Classes are sourced from the FDA label's
# approved use (EGFR TKIs for sensitising mutations, BRAF inhibitors with MEK
# partners, HER2-directed agents, ALK/ROS1 TKIs, PARP inhibitors, CDK4/6
# inhibitors, PI3K/AKT, mTOR, KIT/PDGFRA TKIs).
_DRUG_CLASSES: tuple[frozenset[str], ...] = (
    frozenset({"erlotinib", "gefitinib", "afatinib", "dacomitinib", "osimertinib",
               "mobocertinib", "rociletinib", "amivantamab", "sunvozertinib",
               "poziotinib", "zorifertinib"}),
    frozenset({"dabrafenib", "vemurafenib", "encorafenib", "trametinib",
               "binimetinib", "cobimetinib", "selumetinib"}),
    frozenset({"trastuzumab", "pertuzumab", "ado", "fam", "lapatinib", "tucatinib",
               "neratinib"}),
    frozenset({"alectinib", "brigatinib", "ceritinib", "crizotinib", "lorlatinib",
               "entrectinib"}),
    frozenset({"olaparib", "rucaparib", "niraparib", "talazoparib"}),
    frozenset({"palbociclib", "abemaciclib", "ribociclib"}),
    frozenset({"alpelisib", "capivasertib"}),
    frozenset({"everolimus", "temsirolimus"}),
    frozenset({"imatinib", "sunitinib", "regorafenib", "avapritinib", "ripretinib"}),
    frozenset({"sotorasib", "adagrasib"}),
    frozenset({"selpercatinib", "pralsetinib", "vandetanib", "cabozantinib"}),
    frozenset({"capmatinib", "tepotinib", "crizotinib", "cabozantinib", "tivozanib"}),
    frozenset({"pazopanib", "sunitinib", "cabozantinib", "axitinib", "lenvatinib", "tivozanib", "sorafenib"}),
    frozenset({"larotrectinib", "entrectinib"}),
    frozenset({"ivosidenib", "enasidenib"}),
    frozenset({"vismodegib", "sonidegib"}),
    frozenset({"ibrutinib", "acalabrutinib", "zanubrutinib"}),
    frozenset({"dasatinib", "nilotinib", "ponatinib", "bosutinib", "asciminib"}),
)


def _same_class(a: str, b: str) -> bool:
    a = (a or "").strip().lower().split()[0] if a else ""
    b = (b or "").strip().lower().split()[0] if b else ""
    for cls in _DRUG_CLASSES:
        if a in cls and b in cls:
            return True
    return False


def ranker_score(records: list[dict], results: list[dict]) -> dict:
    by_pid = {r["patient_id"]: r for r in results}
    exact_hits = 0
    class_hits = 0
    with_pred = 0
    true_misses = []
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
            exact_hits += 1
        elif any(_same_class(a, b) for a in got for b in top3):
            class_hits += 1
        else:
            true_misses.append({"patient_id": rec["patient_id"], "top3": res.get("pipeline_top3"),
                                "received": sorted(rec.get("targeted_drugs") or [])})
    return {
        "benchmarkable_patients": sum(1 for r in records if _label(r)["verdict"] == "hit"),
        "ran_on": with_pred,
        "exact_top3_hits": exact_hits,
        "class_equivalent_hits": class_hits,
        "same_class_hit_rate": exact_hits + class_hits,
        "miss_examples": true_misses[:10],
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
    print(f"  unevaluable (no selecting alteration under label): {uneval}")
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
        n = rs["ran_on"] or 1
        print(f"  exact drug in top 3:              "
              f"{rs['exact_top3_hits']} ({100 * rs['exact_top3_hits'] / n:.1f}%)")
        print(f"  same-class drug in top 3:         "
              f"{rs['same_class_hit_rate']} ({100 * rs['same_class_hit_rate'] / n:.1f}%)")
        print(f"  class-equivalent additions:       "
              f"{rs['class_equivalent_hits']} (same molecular target, "
              "different drug in the class)")
        if rs["miss_examples"]:
            print("  example true misses (no class match):")
            for m in rs["miss_examples"][:5]:
                print(f"    {m['patient_id']}: top3={m['top3']} received={m['received']}")


if __name__ == "__main__":
    main()
