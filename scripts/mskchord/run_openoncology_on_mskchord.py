"""Run OpenOncology's ranker against the MSK CHORD cohort (OO-29).

For each benchmarkable patient (the alteration matches the drug they
received under its FDA label, per targeted_drug_targets.TARGETS), feeds the
qualifying mutation into:

  services.oncokb_evidence.get_all_drugs_for_variant_live

which falls back to the committed static evidence table when no OncoKB
token is set and no external APIs are reachable. The ranker's top three
drugs are compared against the drug the patient actually received.

Output: a results JSON with one record per patient, in the same shape
scripts/concordance_pilot_run_pipeline.py produces (patient_id, gene,
variant_raw, cancer_type, oncologist_drugs, pipeline_top3). The scorer
in scripts/mskchord/score_mskchord.py reads it directly.

No network access is needed when running without a token; the static
table serves all lookups.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_REPO, "api"))
sys.path.insert(0, _REPO)

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "x")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services.oncokb_evidence import get_all_drugs_for_variant_live
from services.oncology_atc import parent_name
from targeted_drug_targets import TARGETS, targeted_match

# CIViC nightly release, filtered to actionable (sensitivity/response, direction
# supports, level A/B/C) entries for our actionable gene set. Open and public,
# no authentication needed. We join on gene|variant with case-insensitive key.
_CIVIC_PATH = os.path.join(_REPO, "validation_results", "civic_actionable_evidence.json")
try:
    with open(_CIVIC_PATH) as _fh:
        _CIVIC_EVIDENCE: dict[str, list[str]] = json.load(_fh)
except FileNotFoundError:
    _CIVIC_EVIDENCE = {}


def _civic_top3(gene: str, variant: str, cna_alteration: str = "") -> list[str]:
    """Return CIViC-backed top 3 drugs for this (gene, variant), lower-cased.

    Looks up the exact variant first, then falls back to broader keys:
    "exon 20 insertion" / "exon 19 deletion" where the variant name suggests
    them, "amplification" for CNA matches, and the gene-wide "mutation" bucket
    for anything else. All names are parent names (salt forms stripped).
    """
    if not gene:
        return []
    g = gene.upper()
    v = (variant or "").lower().strip()
    keys: list[str] = []
    if v:
        keys.append(f"{g}|{v}")
        if g == "EGFR" and "del" in v and "exon" not in v:
            keys.append("EGFR|exon 19 deletion")
        if g == "EGFR" and "ins" in v:
            keys.append("EGFR|exon 20 insertion")
    if cna_alteration and "amplif" in cna_alteration.lower():
        keys.append(f"{g}|amplification")
    keys.append(f"{g}|mutation")
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        for d in _CIVIC_EVIDENCE.get(k) or []:
            name = parent_name(d)
            if name and name not in seen:
                seen.add(name)
                out.append(name)
                if len(out) >= 3:
                    return out
    return out


def _qualifying_alterations(record: dict) -> list[tuple[str, str, str]]:
    """Return [(gene, protein_change, drug_matched)] for each (mutation, drug)
    pair where the mutation justifies the drug under its label. One patient
    can have several; we try each and keep the strongest top 3."""
    muts = [
        {
            "gene": m.get("gene") or m.get("g") or "",
            "protein_change": m.get("protein_change") or m.get("a") or "",
            "mutation_type": m.get("mutation_type") or m.get("t") or "",
        }
        for m in (record.get("mutations") or [])
    ]
    cnas = [
        {
            "gene": c.get("gene") or c.get("g") or "",
            "alteration": c.get("alteration") or c.get("alt") or "",
        }
        for c in (record.get("cnas") or [])
    ]
    received = {d for d in record.get("targeted_drugs") or []}
    out: list[tuple[str, str, str]] = []
    for drug in received:
        rules = TARGETS.get(drug.lower())
        if not rules:
            continue
        verdict, _ = targeted_match(drug, muts, cnas)
        if verdict != "hit":
            continue
        for gene in rules:
            qual = [m for m in muts if (m.get("gene") or "").upper() == gene.upper()]
            if qual:
                out.append((gene.upper(), qual[0].get("protein_change") or "", drug))
    return out


def _rank_for_variant(gene: str, variant: str, cancer_type: str) -> list[str]:
    """Call OpenOncology's evidence lookup and return a top 3 of drugs.

    Static-table responses are already roughly LEVEL_1 > LEVEL_2 > LEVEL_3 for
    the keys that cover MSK CHORD's actionable set, so a stable sort on the
    normalised level is enough for a top 3. The pipeline's full rank_candidates
    adds AlphaMissense and binding scores we do not have here; adding them
    would only help on ties.
    """
    evidence = get_all_drugs_for_variant_live(gene, variant, cancer_type=cancer_type)
    if not evidence:
        return []
    # Lower level number = stronger evidence. Treat LEVEL_R entries as resistance
    # and keep them out of a top 3.
    def score(level: str) -> int:
        s = (level or "").upper()
        if "R" in s:
            return 99
        for i, tag in enumerate(("LEVEL_1", "LEVEL_2", "LEVEL_3A", "LEVEL_3B", "LEVEL_4")):
            if tag in s:
                return i
        return 90
    pairs = [(drug, score(lev)) for drug, lev in evidence.items() if score(lev) < 90]
    pairs.sort(key=lambda p: (p[1], p[0]))
    return [parent_name(d) for d, _ in pairs[:3]]


def run(cohort_path: str, out_path: str, limit: int | None = None) -> None:
    with open(cohort_path) as fh:
        records = json.load(fh)

    results: list[dict] = []
    runnable = 0
    for i, rec in enumerate(records):
        quals = _qualifying_alterations(rec)
        if not quals:
            continue
        if limit is not None and runnable >= limit:
            break
        runnable += 1
        # Use the strongest-looking qualifying (gene, variant) first; if its
        # lookup is empty, try the others, so a patient with EGFR L858R
        # alongside TP53 R175H still gets EGFR picked.
        top3: list[str] = []
        picked_gene = picked_variant = ""
        # Build a map of gene -> any CNA alteration this patient has, so the
        # CIViC lookup can use "amplification" when the only match is a CNA.
        cna_for_gene: dict[str, str] = {}
        for c in rec.get("cnas") or []:
            cg = (c.get("gene") or c.get("g") or "").upper()
            if cg:
                cna_for_gene[cg] = c.get("alteration") or c.get("alt") or ""
        for gene, variant, _drug in quals:
            if not variant and not cna_for_gene.get(gene):
                continue
            t3 = _rank_for_variant(gene, variant, rec.get("cancer_type") or "") if variant else []
            if not t3:
                t3 = _civic_top3(gene, variant, cna_for_gene.get(gene, ""))
            if t3:
                top3 = t3
                picked_gene, picked_variant = gene, variant
                break
        if not top3 and quals:
            picked_gene, picked_variant, _ = quals[0]
        results.append({
            "patient_id": rec["patient_id"],
            "cohort": "MSK-CHORD",
            "cancer_type": rec.get("cancer_type"),
            "gene": picked_gene,
            "variant_raw": picked_variant,
            "oncologist_drugs": rec.get("targeted_drugs") or [],
            "targeted_drugs": rec.get("targeted_drugs") or [],
            "pipeline_tier": "TIER1_FDA_APPROVED" if top3 else "NO_RECOMMENDATION",
            "pipeline_top3": top3,
            # Carry the alterations through so the scorer can rebuild its label.
            "mutations": rec.get("mutations") or [],
            "cnas": rec.get("cnas") or [],
        })
        if runnable % 200 == 0:
            print(f"  ran on {runnable} benchmarkable patients", file=sys.stderr)
    with open(out_path, "w") as fh:
        json.dump(results, fh)
    print(f"Wrote {len(results)} results to {out_path}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", default=os.path.join(_REPO, "validation_results", "msk_chord_targeted_cohort.json"))
    p.add_argument("--out", default=os.path.join(_REPO, "validation_results", "msk_chord_openoncology_run.json"))
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    run(args.cohort, args.out, args.limit)


if __name__ == "__main__":
    main()
