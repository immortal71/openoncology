"""How much of the NCI-MATCH concordance figure is generalisation, not lookup.

THE QUESTION THIS ANSWERS
-------------------------
docs/BENCHMARK_NCI_MATCH.md reports 40.6% exact Top-3 and 71.9% class Top-3
against NCI-MATCH subprotocol arms. That answer key is genuinely independent of
anything OpenOncology produced: it is an expert committee's published
biomarker-to-drug assignment, fetched from ClinicalTrials.gov. It is not the F5
defect, where the key was reverse-engineered from the system's own inputs.

But independent-of-our-output is not the same as independent-of-our-evidence.
NCI-MATCH arms and OpenOncology's actionability table are both distillations of
the same clinical literature. If every arm the engine gets right is an arm whose
gene-drug pair was already sitting in the static table, then the benchmark
measures whether the engine can read its own table and order the result. That is
worth knowing, and it is a much weaker claim than "picks the drug an expert
committee picked".

So this splits the scored arms in two:

  contained    — the assigned drug is already in the evidence table for that gene
  independent  — it is not, so a hit had to come from the repurposing tiers

and reports concordance separately for each. This is the same split
scripts/validate_ranking_precision.py applies to Precision@3, where the headline
0.7247 became 0.7288 contained against 0.6296 independent, and the second number
is the one that means anything.

WHAT WOULD FALSIFY THE HEADLINE FIGURE
--------------------------------------
If the independent subset scores at or near zero, the headline is a table-read
and should be quoted as one. If it holds up, the engine is doing something the
table alone does not explain. Either way the number stops being ambiguous.

READ THIS BEFORE QUOTING THE NUMBER
-----------------------------------
* The independent subset is small. NCI-MATCH has 38 arms and not all score. A
  percentage over a handful of arms is an observation, not an estimate, and the
  raw counts are reported alongside it for that reason.
* "Contained" is decided by the same lookup the engine uses, so an arm whose
  drug is reachable only through a gene-level fallback counts as contained. That
  biases toward calling arms contained, which understates the independent
  subset rather than flattering it.

Usage:
    python scripts/audit_nci_match_independence.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_RESULTS = _REPO_ROOT / "validation_results" / "nci_match_concordance.json"
_OUT = _REPO_ROOT / "validation_results" / "nci_match_independence.json"


def _drug_is_in_table(gene: str, variant: str, drug: str) -> bool:
    """Whether the evidence table already pairs this drug with this gene."""
    from services.oncokb_evidence import (
        ensure_oncokb_table_loaded,
        get_all_drugs_for_variant,
        lookup_oncokb_level,
    )

    try:
        ensure_oncokb_table_loaded()
    except Exception:
        pass

    if lookup_oncokb_level(gene, variant or "", drug):
        return True
    # Also treat a drug the table offers for this variant as contained, even if
    # the triple lookup misses on alteration spelling.
    try:
        levels = get_all_drugs_for_variant(gene, variant or "")
    except Exception:
        return False
    target = "".join(ch for ch in drug.lower() if ch.isalnum())
    for name in levels:
        norm = "".join(ch for ch in str(name).lower() if ch.isalnum())
        if norm and (norm in target or target in norm):
            return True
    return False


def _rate(hits: int, n: int) -> float | None:
    return round(100.0 * hits / n, 1) if n else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=str(_RESULTS))
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    arms = payload.get("results") or []
    if not arms:
        print("no scored arms in the results file", file=sys.stderr)
        return 1

    buckets: dict[str, list[dict]] = {"contained": [], "independent": []}
    for arm in arms:
        gene = arm.get("gene_used") or arm.get("gene") or ""
        variant = arm.get("variant_used") or ""
        drug = arm.get("assigned_drug") or ""
        bucket = "contained" if _drug_is_in_table(gene, variant, drug) else "independent"
        buckets[bucket].append(arm)
        print(
            f"  {arm.get('arm_id','?'):>4}  {gene:<8} {drug:<24} {bucket}",
            flush=True,
        )

    summary = {"total_scored": len(arms)}
    for name, rows in buckets.items():
        exact = sum(1 for a in rows if a.get("exact_hit"))
        klass = sum(1 for a in rows if a.get("class_hit"))
        summary[name] = {
            "n": len(rows),
            "exact_top3": exact,
            "class_top3": klass,
            "exact_top3_pct": _rate(exact, len(rows)),
            "class_top3_pct": _rate(klass, len(rows)),
        }

    out = {
        "audit": "nci_match_arm_independence",
        "question": (
            "How much of the NCI-MATCH concordance is generalisation rather "
            "than reading the engine's own evidence table?"
        ),
        "source_results": str(Path(args.results).name),
        "summary": summary,
        "caveats": [
            "The independent subset is small; counts matter more than percentages.",
            "Gene-level fallback counts an arm as contained, which understates "
            "the independent subset rather than flattering it.",
            "NCI-MATCH is independent of this system's output, but both it and "
            "the evidence table distil the same clinical literature.",
        ],
        "arms": {
            name: [
                {
                    "arm_id": a.get("arm_id"),
                    "gene": a.get("gene_used") or a.get("gene"),
                    "assigned_drug": a.get("assigned_drug"),
                    "exact_hit": a.get("exact_hit"),
                    "class_hit": a.get("class_hit"),
                }
                for a in rows
            ]
            for name, rows in buckets.items()
        },
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print()
    print(f"  scored arms: {summary['total_scored']}")
    for name in ("contained", "independent"):
        b = summary[name]
        print(
            f"  {name:<12} n={b['n']:<3} exact {b['exact_top3']}/{b['n']} "
            f"({b['exact_top3_pct']}%)   class {b['class_top3']}/{b['n']} "
            f"({b['class_top3_pct']}%)"
        )
    print()
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
