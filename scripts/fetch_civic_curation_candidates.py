"""Fetch sourced evidence candidates from CIViC for the gaps in our table.

WHY THIS EXISTS
---------------
Several buckets in _LEVEL_TABLE carry a key with nothing in it: ERBB2
OVEREXPRESSION, TERT PROMOTER, MGMT METHYLATION, STK11, DDR2, AXL, CCNE1,
FGFR4, MDM2, and the missing PTCH1/VHL DELETION bucket. Each one is a real
clinical finding that currently reaches no drug at all.

Those gaps were left alone deliberately, because writing evidence from memory
puts a drug recommendation in front of a cancer patient with nothing behind
it. That objection is about provenance, not about difficulty, so the answer is
to source the evidence rather than to keep declining.

CIViC is an open, expert-curated variant interpretation database, and every
evidence item carries a PubMed citation. This script pulls the accepted
PREDICTIVE items for the genes we are missing and writes them to a review file
with the citation attached.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not write into _LEVEL_TABLE. Output is a candidate file for a
clinician to approve, because mapping CIViC's A-to-E evidence levels onto
OncoKB's LEVEL_1 to LEVEL_4 is a clinical judgement about strength of
evidence, not a lookup. An automated mapping would launder someone else's
confidence into ours.

The suggested_oncokb_level field is a starting point for that review and is
labelled as such in the output. Nothing here reaches a patient until a human
moves it into the table.

Usage:
    python scripts/fetch_civic_curation_candidates.py
    python scripts/fetch_civic_curation_candidates.py --gene ERBB2
"""
from __future__ import annotations

import argparse
import json
import os
import time

import httpx

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_OUT = os.path.join(_REPO_ROOT, "validation_results", "civic_curation_candidates.json")
_API = "https://civicdb.org/api/graphql"

# Genes whose buckets are empty or missing entirely. Sourced from the audit
# scripts in this directory, not hand-picked.
TARGET_GENES = [
    "ERBB2", "TERT", "MGMT", "STK11", "DDR2", "AXL", "CCNE1", "FGFR4",
    "MDM2", "PTCH1", "VHL",
]

# CIViC evidence levels are about study design, OncoKB levels are about
# clinical actionability. They are not the same axis, so this is a hint for a
# reviewer rather than a conversion.
_LEVEL_HINT = {
    "A": "LEVEL_1 candidate (validated association)",
    "B": "LEVEL_2 candidate (clinical evidence)",
    "C": "LEVEL_3B candidate (case study)",
    "D": "LEVEL_4 candidate (preclinical)",
    "E": "inferential, likely not actionable",
}

_QUERY = """
query($after: String) {
  evidenceItems(first: 100, status: ACCEPTED, evidenceType: PREDICTIVE, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      evidenceLevel
      evidenceDirection
      significance
      therapies { name }
      molecularProfile { name }
      disease { name }
      source { citationId sourceType }
    }
  }
}
"""


def _fetch_all(tries: int = 4) -> list[dict]:
    nodes: list[dict] = []
    after = None
    while True:
        payload = None
        for attempt in range(tries):
            try:
                resp = httpx.post(
                    _API, json={"query": _QUERY, "variables": {"after": after}},
                    timeout=90,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    break
            except Exception:  # noqa: BLE001 - retried
                pass
            time.sleep(3 * (attempt + 1))
        if payload is None:
            raise SystemExit("CIViC unreachable; nothing written")
        if "errors" in payload:
            raise SystemExit(f"CIViC query error: {payload['errors']}")
        block = payload["data"]["evidenceItems"]
        nodes.extend(block["nodes"])
        print(f"  fetched {len(nodes)}")
        if not block["pageInfo"]["hasNextPage"]:
            break
        after = block["pageInfo"]["endCursor"]
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gene", action="append", default=None,
                        help="Restrict to one gene (repeatable)")
    args = parser.parse_args()
    genes = [g.upper() for g in (args.gene or TARGET_GENES)]

    print("Fetching accepted PREDICTIVE evidence from CIViC...")
    nodes = _fetch_all()

    candidates: list[dict] = []
    for node in nodes:
        profile = (node.get("molecularProfile") or {}).get("name") or ""
        upper = profile.upper()
        matched = next((g for g in genes if g in upper.split()
                        or upper.startswith(g + " ")
                        or f" {g} " in f" {upper} "), None)
        if not matched:
            continue
        therapies = [t["name"] for t in (node.get("therapies") or []) if t.get("name")]
        if not therapies:
            continue
        source = node.get("source") or {}
        level = node.get("evidenceLevel") or ""
        candidates.append({
            "gene": matched,
            "molecular_profile": profile,
            "disease": (node.get("disease") or {}).get("name"),
            "therapies": therapies,
            "civic_evidence_level": level,
            "evidence_direction": node.get("evidenceDirection"),
            "significance": node.get("significance"),
            "citation": f"{source.get('sourceType')}:{source.get('citationId')}",
            "suggested_oncokb_level": _LEVEL_HINT.get(level, "review required"),
            "review_status": "PENDING_CLINICAL_REVIEW",
        })

    candidates.sort(key=lambda c: (c["gene"], c["civic_evidence_level"]))
    by_gene: dict[str, int] = {}
    for c in candidates:
        by_gene[c["gene"]] = by_gene.get(c["gene"], 0) + 1

    os.makedirs(os.path.dirname(_OUT), exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump({
            "description": (
                "Sourced evidence candidates from CIViC for genes whose buckets "
                "in _LEVEL_TABLE are empty or missing. Every entry carries a "
                "citation."
            ),
            "warning": (
                "NOT evidence. Nothing here has been reviewed, and CIViC's A-to-E "
                "levels are about study design while OncoKB's levels are about "
                "clinical actionability, so suggested_oncokb_level is a prompt "
                "for a reviewer rather than a conversion. Do not copy into "
                "_LEVEL_TABLE without clinical sign-off."
            ),
            "source": "https://civicdb.org",
            "generated_by": "scripts/fetch_civic_curation_candidates.py",
            "genes_targeted": genes,
            "candidates_by_gene": by_gene,
            "n_candidates": len(candidates),
            "candidates": candidates,
        }, fh, indent=2)

    print()
    print(f"wrote {_OUT}")
    print(f"  {len(candidates)} candidates across {len(by_gene)} gene(s)")
    for gene in sorted(by_gene):
        print(f"    {gene:<8} {by_gene[gene]}")
    missing = [g for g in genes if g not in by_gene]
    if missing:
        print(f"  no CIViC predictive evidence found for: {', '.join(missing)}")
        print("  those remain genuine curation gaps, not lookup failures")


if __name__ == "__main__":
    main()
