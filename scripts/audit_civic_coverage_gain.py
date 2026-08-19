"""What CIViC would add to the actionability table, measured before adding it.

WHY THIS EXISTS
---------------
scripts/audit_nci_match_independence.py found that the NCI-MATCH concordance
figure is carried almost entirely by arms whose gene-drug pair was already in the
evidence table: 66.7% exact Top-3 on those, 7.1% on the fourteen arms where the
pair was not. The engine ranks what it holds and rarely reaches past it.

The obvious response is to hold more. `data/civic_evidence.tsv` is a 4 MB CIViC
bulk export sitting in this repository, used today only for live per-variant
lookups in services/civic.py, never loaded into the actionability table. The
static table it would supplement carries 335 entries, and is what serves every
request whenever OncoKB's public dump 401s, which is currently always.

The evidence table decides which drugs reach a patient's report. Changing it is
the highest-consequence edit available in this codebase, so this script measures
the change instead of making it. It answers one question: how many of the arms
the engine currently misses would become reachable if CIViC A/B evidence were
loaded?

If the answer is small, loading CIViC is not worth the risk it carries. If it is
large, the case is made with a number rather than an intuition.

WHAT IS AND IS NOT COUNTED
--------------------------
Only CIViC evidence levels A and B are counted. A is validated association, B is
clinical evidence; those are the tiers comparable to the OncoKB L1/L2 entries
that drive recommendations. C, D and E are case study, preclinical and
inferential, and loading them as actionable would inflate what the system claims
rather than what it knows. That is H5, and it is the reason this audit reports
the A/B count separately from the total.

Only Predictive evidence with a Supports direction is counted, because that is
the only kind that answers "this alteration implies this therapy". Diagnostic,
prognostic and oncogenic evidence say something real and say nothing about drug
choice.

READ THIS BEFORE ACTING ON THE NUMBER
-------------------------------------
Coverage is not correctness. An arm becoming reachable means the pair exists in
CIViC, not that the ranker would surface it in the top three, and not that the
resulting recommendation would be right. The number here is an upper bound on
the gain, and the actual gain can only be measured by loading the data and
rerunning the benchmark.

Usage:
    python scripts/audit_civic_coverage_gain.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_CIVIC = _REPO_ROOT / "data" / "civic_evidence.tsv"
_INDEPENDENCE = _REPO_ROOT / "validation_results" / "nci_match_independence.json"
_OUT = _REPO_ROOT / "validation_results" / "civic_coverage_gain.json"

_ACCEPTED_LEVELS = {"A", "B"}


def _norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _gene_from_molecular_profile(profile: str) -> str:
    """CIViC molecular_profile looks like 'EGFR L858R' or 'BRAF V600E'."""
    token = (profile or "").strip().split()
    return token[0].upper() if token else ""


def _therapies(raw: str) -> list[str]:
    """CIViC therapies is a comma or semicolon separated list."""
    return [t.strip() for t in re.split(r"[;,]", raw or "") if t.strip()]


def load_civic_pairs(path: Path) -> tuple[set[tuple[str, str]], dict[str, int]]:
    """Return {(gene, normalised drug)} for accepted evidence, plus counters."""
    pairs: set[tuple[str, str]] = set()
    stats = {
        "rows": 0,
        "predictive_supports": 0,
        "level_ab": 0,
        "accepted_rows": 0,
        "distinct_pairs": 0,
        "distinct_genes": 0,
    }
    genes: set[str] = set()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            stats["rows"] += 1
            if (row.get("evidence_type") or "").strip().lower() != "predictive":
                continue
            if (row.get("evidence_direction") or "").strip().lower() != "supports":
                continue
            stats["predictive_supports"] += 1
            level = (row.get("evidence_level") or "").strip().upper()[:1]
            if level not in _ACCEPTED_LEVELS:
                continue
            stats["level_ab"] += 1
            gene = _gene_from_molecular_profile(row.get("molecular_profile", ""))
            if not gene:
                continue
            drugs = _therapies(row.get("therapies", ""))
            if not drugs:
                continue
            stats["accepted_rows"] += 1
            genes.add(gene)
            for drug in drugs:
                pairs.add((gene, _norm(drug)))
    stats["distinct_pairs"] = len(pairs)
    stats["distinct_genes"] = len(genes)
    return pairs, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--civic", default=str(_CIVIC))
    ap.add_argument("--independence", default=str(_INDEPENDENCE))
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    civic_path = Path(args.civic)
    if not civic_path.exists():
        print(f"missing {civic_path}", file=sys.stderr)
        return 1

    pairs, stats = load_civic_pairs(civic_path)
    print(f"  CIViC rows                 : {stats['rows']:,}")
    print(f"  predictive + supports      : {stats['predictive_supports']:,}")
    print(f"  of those, level A or B     : {stats['level_ab']:,}")
    print(f"  distinct gene-drug pairs   : {stats['distinct_pairs']:,}")
    print(f"  distinct genes             : {stats['distinct_genes']:,}")

    payload: dict[str, object] = {
        "audit": "civic_coverage_gain",
        "question": (
            "How many NCI-MATCH arms the engine currently misses would become "
            "reachable if CIViC level A/B predictive evidence were loaded?"
        ),
        "civic_source": civic_path.name,
        "civic_stats": stats,
        "accepted_evidence_levels": sorted(_ACCEPTED_LEVELS),
        "caveats": [
            "Coverage is not correctness: a reachable pair is not a top-three "
            "recommendation and not a right one. This is an upper bound.",
            "Only predictive/supports evidence at level A or B is counted. "
            "Loading C, D or E as actionable would inflate what the system "
            "claims relative to what it knows.",
        ],
    }

    indep_path = Path(args.independence)
    if indep_path.exists():
        indep = json.loads(indep_path.read_text(encoding="utf-8"))
        missed = [
            a
            for a in indep.get("arms", {}).get("independent", [])
            if not a.get("exact_hit")
        ]
        covered, uncovered = [], []
        for arm in missed:
            gene = (arm.get("gene") or "").upper()
            drug = _norm(arm.get("assigned_drug") or "")
            hit = any(
                g == gene and (d in drug or drug in d) for g, d in pairs if d
            )
            (covered if hit else uncovered).append(arm)
        payload["nci_match"] = {
            "independent_arms_missed_exact": len(missed),
            "would_become_reachable": len(covered),
            "still_absent": len(uncovered),
            "reachable_arms": [
                {"arm_id": a.get("arm_id"), "gene": a.get("gene"),
                 "assigned_drug": a.get("assigned_drug")}
                for a in covered
            ],
            "absent_arms": [
                {"arm_id": a.get("arm_id"), "gene": a.get("gene"),
                 "assigned_drug": a.get("assigned_drug")}
                for a in uncovered
            ],
        }
        print()
        print(f"  NCI-MATCH independent arms missed exactly : {len(missed)}")
        print(f"    CIViC A/B would make reachable          : {len(covered)}")
        print(f"    still absent from CIViC A/B             : {len(uncovered)}")
        for a in covered:
            print(f"      + {a.get('arm_id')} {a.get('gene')} {a.get('assigned_drug')}")
    else:
        print(f"\n  (no {indep_path.name}; run audit_nci_match_independence.py first)")

    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print()
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
