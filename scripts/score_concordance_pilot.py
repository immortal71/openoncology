"""Score a concordance pilot results file, keeping the two kinds of match apart (OO-28).

    python scripts/score_concordance_pilot.py validation_results/real_patient_concordance_pilot_2026-07-28.json
    python scripts/score_concordance_pilot.py gated_results.json

Reports:
  1. Top-3 concordance as published: any of pipeline_top3 among the drugs the
     patient received.
  2. The same, split into gene-matched hits and hits that are classical
     chemotherapy (WHO ATC L01A-L01D, L01XA). A chemotherapy "hit" from the
     gene-to-drug tier means the tool suggested chemo for a gene and the
     patient happened to get chemo; it says nothing about the mutation.
  3. Standard-of-care coverage: whether services/standard_of_care.py lists a
     drug the patient received for their cancer type. This measures whether
     the standard-care menu is right, not a decision. It is a different claim
     from (1) and must be reported as such.

No network access: ATC codes come from the committed offline cache.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "api"))
sys.path.insert(0, _REPO)

from services.oncology_atc import is_untargeted_cytotoxic, parent_name
from services.standard_of_care import drug_names


def _received(row: dict) -> set[str]:
    return {parent_name(d) for d in row.get("oncologist_drugs") or []}


def _first_word(name: str) -> str:
    return parent_name(name).split()[0] if name else ""


def _matches(pick: str, received: set[str]) -> bool:
    p = parent_name(pick)
    return p in received or _first_word(p) in {r.split()[0] for r in received if r}


def score(rows: list[dict]) -> dict:
    with_pick = [r for r in rows if r.get("pipeline_top3")]
    hits = gene_matched = chemo_only = 0
    for r in with_pick:
        got = _received(r)
        matched = [d for d in r["pipeline_top3"] if _matches(d, got)]
        if not matched:
            continue
        hits += 1
        if all(is_untargeted_cytotoxic(d, allow_network=False) for d in matched):
            chemo_only += 1
        else:
            gene_matched += 1

    soc_rows = [r for r in rows if drug_names(r.get("cancer_type"))]
    soc_hits = 0
    for r in soc_rows:
        menu = drug_names(r.get("cancer_type"))
        got = _received(r)
        if any(g in menu or g.split()[0] in menu for g in got if g):
            soc_hits += 1

    return {
        "patients": len(rows),
        "with_a_pick": len(with_pick),
        "top3_hits": hits,
        "top3_hits_gene_matched": gene_matched,
        "top3_hits_chemotherapy_coincidence": chemo_only,
        "standard_of_care_patients": len(soc_rows),
        "standard_of_care_covered": soc_hits,
    }


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        _REPO, "validation_results", "real_patient_concordance_pilot_2026-07-28.json"
    )
    with open(path) as fh:
        rows = json.load(fh)
    s = score(rows)
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else f"{a}/0"
    print(f"Patients: {s['patients']}, with a pick: {s['with_a_pick']}")
    print(f"Top-3 concordance, as published:        {pct(s['top3_hits'], s['with_a_pick'])}")
    print(f"  of which gene-matched:                 {s['top3_hits_gene_matched']}")
    print(f"  of which chemotherapy coincidence:     {s['top3_hits_chemotherapy_coincidence']}")
    print(f"Standard-of-care list covered the drug:  "
          f"{pct(s['standard_of_care_covered'], s['standard_of_care_patients'])} "
          "(menu coverage, not a ranked decision)")


if __name__ == "__main__":
    main()
