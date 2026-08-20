"""Where the NCI-MATCH misses actually come from: Tier 1, Tier 2, or by design.

WHY THIS EXISTS
---------------
scripts/audit_nci_match_independence.py split the NCI-MATCH arms on whether the
assigned drug was already in the evidence table, and reported 7.1% exact Top-3
on the arms where it was not. That was read as "the engine rarely generalises
past its own table".

That reading was wrong, and this script is the correction.

`run_pipeline` in scripts/benchmark_nci_match.py calls only
`get_all_drugs_for_variant_live`, which is OncoKB live API plus the curated
static table. It never calls the Tier 2 repurposing path (OpenTargets, DGIdb)
that the TCGA concordance pilot explicitly did call. So the benchmark asks the
evidence table a question, and "independent" was defined as "not in the evidence
table". A near-zero score on that subset is close to circular: the subset was
constructed to exclude what the only tier being queried could answer.

The engine has a generalisation path. The benchmark never invoked it.

WHAT THIS MEASURES INSTEAD
--------------------------
For every arm the benchmark missed, it asks three separate questions:

  tier1     — is the assigned drug in the evidence table at all?
  tier2     — do OpenTargets or DGIdb return it for that gene?
  approved  — is it an approved drug, or an investigational compound?

The third matters more than it looks. NCI-MATCH is a trial-matching protocol and
several arms assign Phase 1/2 investigational agents that never reached
approval. This engine filters Tier 2 to approved drugs on purpose, because
recommending an unapproved compound to a patient is not a repurposing
suggestion. An arm assigning such a compound is not a miss, it is out of scope,
and counting it as a miss understates the engine exactly as counting it as a hit
would overstate it.

So the misses separate into three groups, and only one of them is a defect:

  reachable-but-not-ranked  — Tier 2 returns the drug, the ranker did not
                              surface it in the top three. A real ranking defect.
  not-retrieved             — no tier returns it. A coverage defect.
  out-of-scope              — investigational, deliberately not recommended.

READ THIS BEFORE QUOTING THE NUMBER
-----------------------------------
Live calls to OpenTargets and DGIdb make this run non-deterministic across
days; both are live services whose contents change. Approval status is read from
whatever those services report rather than from a regulatory source, so it is
their opinion, not the FDA's.

Usage:
    python scripts/diagnose_nci_match_tier2.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_INDEPENDENCE = _REPO_ROOT / "validation_results" / "nci_match_independence.json"
_OUT = _REPO_ROOT / "validation_results" / "nci_match_tier2_diagnosis.json"


def _norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _matches(target: str, name: str) -> bool:
    a, b = _norm(target), _norm(name)
    return bool(a and b and (a in b or b in a))


def _tier1_drugs(gene: str, variant: str) -> dict[str, str]:
    from services.oncokb_evidence import get_all_drugs_for_variant_live

    try:
        return get_all_drugs_for_variant_live(
            gene, variant, cancer_type=None, alphamissense_score=1.0
        ) or {}
    except Exception as exc:
        print(f"      tier1 error: {exc}", file=sys.stderr)
        return {}


async def _tier2_drugs(gene: str) -> list[dict]:
    """The repurposing path the benchmark never called."""
    from services.dgidb import get_interactions
    from services.opentargets import get_drugs_for_target, get_target_id

    out: list[dict] = []
    try:
        ensg = await get_target_id(gene)
        if ensg:
            for d in await get_drugs_for_target(ensg, max_drugs=50) or []:
                out.append(
                    {
                        "drug_name": d.get("drug_name"),
                        "source": "OpenTargets",
                        "max_phase": d.get("max_phase"),
                        "is_approved": d.get("is_approved"),
                    }
                )
    except Exception as exc:
        print(f"      opentargets error: {exc}", file=sys.stderr)
    try:
        for d in await get_interactions(gene, approved_only=False) or []:
            out.append(
                {
                    "drug_name": d.get("drug_name"),
                    "source": "DGIdb",
                    "max_phase": d.get("max_phase"),
                    "is_approved": d.get("is_approved"),
                }
            )
    except Exception as exc:
        print(f"      dgidb error: {exc}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--independence", default=str(_INDEPENDENCE))
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    data = json.loads(Path(args.independence).read_text(encoding="utf-8"))
    arms = [a for a in data.get("arms", {}).get("independent", []) if not a.get("exact_hit")]
    print(f"  diagnosing {len(arms)} missed independent arms\n")

    rows = []
    for arm in arms:
        gene = (arm.get("gene") or "").upper()
        drug = arm.get("assigned_drug") or ""
        print(f"  {arm.get('arm_id'):>4} {gene:<8} {drug}")

        t1 = _tier1_drugs(gene, "")
        in_t1 = any(_matches(drug, name) for name in t1)

        t2 = asyncio.run(_tier2_drugs(gene))
        hits = [d for d in t2 if _matches(drug, d.get("drug_name") or "")]
        in_t2 = bool(hits)
        approved = any(bool(h.get("is_approved")) for h in hits) if hits else None
        phases = sorted(
            {str(h.get("max_phase")) for h in hits if h.get("max_phase") is not None}
        )

        if in_t2 and approved:
            verdict = "reachable_but_not_ranked"
        elif in_t2 and not approved:
            verdict = "out_of_scope_investigational"
        elif in_t1:
            verdict = "reachable_but_not_ranked"
        else:
            verdict = "not_retrieved"

        print(
            f"        tier1={in_t1}  tier2={in_t2}  approved={approved}  "
            f"phases={phases}  -> {verdict}"
        )
        rows.append(
            {
                "arm_id": arm.get("arm_id"),
                "gene": gene,
                "assigned_drug": drug,
                "in_tier1_evidence_table": in_t1,
                "in_tier2_repurposing": in_t2,
                "tier2_reports_approved": approved,
                "tier2_max_phases": phases,
                "tier2_candidate_count": len(t2),
                "verdict": verdict,
            }
        )

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    payload = {
        "audit": "nci_match_tier2_diagnosis",
        "corrects": (
            "audit_nci_match_independence.py, whose 7.1% independent-subset "
            "figure was read as poor generalisation. The benchmark's run_pipeline "
            "calls only get_all_drugs_for_variant_live, which is OncoKB plus the "
            "static table, so the Tier 2 repurposing path was never invoked and "
            "the independent subset was defined by exclusion from the only tier "
            "being queried."
        ),
        "arms_diagnosed": len(rows),
        "verdict_counts": counts,
        "rows": rows,
        "caveats": [
            "OpenTargets and DGIdb are live services; this run is not "
            "reproducible byte for byte across days.",
            "Approval status is what those services report, not a regulatory "
            "determination.",
        ],
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    for verdict, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {verdict:<32} {n}")
    print()
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
