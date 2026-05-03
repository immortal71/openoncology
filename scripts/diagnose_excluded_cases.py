"""Diagnostic script for cases excluded from the hard benchmark.

When `run_hard_clinical_benchmark` runs with `enforce_stable_source_coverage=True`
(the default), any sensitivity case whose known drugs are absent from the static
evidence table is excluded to prevent flaky metrics tied to live-API availability.

This script makes those exclusions transparent by:
  1. Re-running the coverage filter with verbose per-case logging.
  2. For each excluded case, showing which known drugs are missing from the
     static table and which co-alterations were checked.
  3. Summarising the exclusion reason so the team can decide whether to:
       a) Add the drug to the static evidence table (preferred if evidence is solid).
       b) Mark the case as expect_empty (if there is genuinely no approved drug).
       c) Accept the exclusion if the drug is truly live-only and volatile.

Usage:
    .venv\\Scripts\\python.exe scripts\\diagnose_excluded_cases.py

Exit codes:
    0 — script ran successfully (some exclusions are expected and informational)
    1 — unexpected error
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, UTC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.services.benchmark import (
    HARD_CLINICAL_CASES,
    _extract_co_alterations,
    _has_stable_source_coverage,
    _is_match,
    _normalise_drug_name_for_context,
)
from api.services.oncokb_evidence import get_all_drugs_for_variant


def _check_case_coverage(case: dict) -> dict:
    """Return a detailed coverage report for a single benchmark case."""
    gene = str(case.get("gene", ""))
    variant = str(case.get("variant", ""))
    known_drugs = case.get("known_drugs", []) or []
    expect_empty = bool(case.get("expect_empty", False))
    co_alterations = _extract_co_alterations(case)

    # Collect all drugs from static table (primary + co-alterations)
    primary_map = get_all_drugs_for_variant(gene, variant, alphamissense_score=1.0)
    merged_map: dict[str, str] = dict(primary_map)
    co_maps: dict[str, dict] = {}
    for co_gene, co_alt in co_alterations.items():
        co_map = get_all_drugs_for_variant(co_gene, co_alt, alphamissense_score=1.0)
        co_maps[f"{co_gene}:{co_alt}"] = co_map
        merged_map.update(co_map)

    covered_known: list[str] = []
    missing_known: list[str] = []
    for drug in known_drugs:
        if any(_is_match(d, [drug]) for d in merged_map.keys()):
            covered_known.append(drug)
        else:
            missing_known.append(drug)

    has_coverage = _has_stable_source_coverage(case, get_all_drugs_for_variant)

    return {
        "case_id": case.get("case_id", "UNKNOWN"),
        "gene": gene,
        "variant": variant,
        "cancer_type": case.get("cancer_type", ""),
        "difficulty": case.get("difficulty", ""),
        "expect_empty": expect_empty,
        "known_drugs": known_drugs,
        "has_stable_coverage": has_coverage,
        "primary_static_drugs": list(primary_map.keys()),
        "co_alterations_checked": co_alterations,
        "co_alteration_drugs": co_maps,
        "covered_known_drugs": covered_known,
        "missing_known_drugs": missing_known,
        "remediation": _suggest_remediation(missing_known, case),
    }


def _suggest_remediation(missing_drugs: list[str], case: dict) -> str:
    if not missing_drugs:
        return "none_needed"
    if len(missing_drugs) == len(case.get("known_drugs", []) or []):
        return (
            "add_to_static_table: all known drugs absent from oncokb_evidence.py; "
            "verify FDA/OncoKB approval status and add the missing entries"
        )
    return (
        f"partial_coverage: {len(missing_drugs)}/{len(case.get('known_drugs',[]))} "
        "known drugs missing from static table; add them or verify against live OncoKB"
    )


def main() -> int:
    cases = HARD_CLINICAL_CASES
    reports = [_check_case_coverage(c) for c in cases]

    included = [r for r in reports if r["has_stable_coverage"]]
    excluded = [r for r in reports if not r["has_stable_coverage"]]
    negatives_always_included = [r for r in reports if r["expect_empty"]]

    print("=" * 72)
    print("HARD BENCHMARK — EXCLUDED-CASE DIAGNOSTIC")
    print("=" * 72)
    print(f"Run at: {datetime.now(UTC).isoformat()}")
    print(f"Total hard cases:         {len(cases)}")
    print(f"  Stable coverage (kept): {len(included)}")
    print(f"  Unstable (excluded):    {len(excluded)}")
    print(f"  Negative controls:      {len(negatives_always_included)}")

    if not excluded:
        print("\nNo cases excluded — full hard set is in play.")
    else:
        print(f"\n{'─' * 72}")
        print(f"EXCLUDED CASES ({len(excluded)})")
        print(f"{'─' * 72}")
        for r in excluded:
            print(f"\nCase: {r['case_id']}")
            print(f"  Gene/variant:  {r['gene']} {r['variant']}  ({r['cancer_type']})")
            print(f"  Difficulty:    {r['difficulty']}")
            print(f"  Known drugs:   {r['known_drugs']}")
            print(f"  Static table:  {r['primary_static_drugs'] or '(empty)'}")
            if r["co_alterations_checked"]:
                print(f"  Co-alts:       {r['co_alterations_checked']}")
                for label, co_map in r["co_alteration_drugs"].items():
                    print(f"    {label}: {list(co_map.keys()) or '(empty)'}")
            print(f"  Covered:       {r['covered_known_drugs']}")
            print(f"  MISSING:       {r['missing_known_drugs']}")
            print(f"  Remediation:   {r['remediation']}")

    print(f"\n{'─' * 72}")
    print("INCLUDED CASE COVERAGE SUMMARY")
    print(f"{'─' * 72}")
    for r in sorted(included, key=lambda x: (x["expect_empty"], x["case_id"])):
        status = "NEG_CTRL" if r["expect_empty"] else "OK"
        missing = f"  [partial: missing {r['missing_known_drugs']}]" if r["missing_known_drugs"] else ""
        print(f"  {r['case_id']:50s} [{status}]{missing}")

    # Write machine-readable artifact
    artifact = {
        "run_at": datetime.now(UTC).isoformat(),
        "total_cases": len(cases),
        "included_count": len(included),
        "excluded_count": len(excluded),
        "excluded": excluded,
        "included_with_partial_coverage": [
            r for r in included if r["missing_known_drugs"]
        ],
    }
    out_path = os.path.join(ROOT, "artifacts", "excluded_cases_diagnostic.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)

    print(f"\nArtifact: {out_path}")
    if excluded:
        print(
            "\nAction required: for each excluded case, add the missing drugs to "
            "api/services/oncokb_evidence.py or change the case to expect_empty=True."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
