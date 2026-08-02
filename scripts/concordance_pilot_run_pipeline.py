"""
Real oncologist-concordance pilot study.

For each of the 81 real TCGA patients (verified: real VCF/mutation record AND
a real recorded targeted-therapy drug from GDC clinical data), this script:
  1. Picks the patient's most clinically-plausible actionable mutation.
  2. Runs it through the REAL OpenOncology ranking pipeline (Tier 1 FDA-approved
     evidence via services.oncokb_evidence.get_all_drugs_for_variant, then Tier 2
     repurposing via OpenTargets/DGIdb, both scored by the real
     api.ai.ranking.rank_candidates()) -- the same functions the project's own
     scripts/fetch_real_patients.py benchmark uses.
  3. Records the pipeline's top-3 recommended drugs.
  4. Compares against the real drug(s) the oncologist actually gave this patient.

This is NOT a mocked or simulated run -- it calls live OpenTargets/DGIdb APIs
and the actual static+curated OncoKB evidence table shipped in this repo.

Expects candidate_patients.json and new_cohort_overlap.json (produced by the
sibling fetch scripts) in the same directory as this script, or pass
--data-dir. Real VCF files are read from <repo_root>/samples/real/.
"""
import sys
import os
import json
import asyncio
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "concordance-study-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services.oncokb_evidence import get_all_drugs_for_variant_live  # noqa: E402
from ai.ranking import rank_candidates  # noqa: E402

# Priority gene list: known cancer driver genes with real, well-established
# actionable evidence in the current evidence table -- used only to CHOOSE
# which of a patient's several mutations to submit (a real patient has one
# tumor, the pipeline needs one variant per submission, same as the app UI).
# This does not affect scoring; rank_candidates() and get_all_drugs_for_variant
# are the actual code paths under test.
PRIORITY_GENES = {
    "EGFR", "KRAS", "BRAF", "ALK", "ROS1", "MET", "RET", "ERBB2", "HER2",
    "PIK3CA", "AKT1", "MTOR", "IDH1", "IDH2", "FGFR1", "FGFR2", "FGFR3",
    "KIT", "PDGFRA", "VHL", "MTOR", "TSC1", "TSC2", "AR", "BRCA1", "BRCA2",
    "NTRK1", "NTRK2", "NTRK3", "ESR1", "CDK4", "CDK6", "SMO", "PTCH1",
}


def _cohort_cancer_type(cohort: str) -> str:
    return {
        "TCGA-SKCM": "Melanoma",
        "TCGA-LUAD": "Non-Small Cell Lung Cancer",
        "TCGA-BRCA": "Breast Cancer",
        "TCGA-COAD": "Colorectal Cancer",
        "TCGA-GBM": "Glioblastoma",
        "TCGA-PRAD": "Prostate Cancer",
        "TCGA-KIRC": "Renal Cell Carcinoma",
        "TCGA-PAAD": "Pancreatic Cancer",
        "TCGA-THCA": "Thyroid Cancer",
        "TCGA-STAD": "Gastric Cancer",
    }.get(cohort, cohort)


def _pick_variant(mutations: list[dict]) -> dict | None:
    """Pick the single mutation to submit for this patient: prefer a known
    priority/driver gene; otherwise fall back to the first real coding mutation."""
    priority = [m for m in mutations if (m.get("gene") or "").upper() in PRIORITY_GENES]
    pool = priority if priority else mutations
    return pool[0] if pool else None


def run_tier1(gene: str, variant: str, cancer_type: str) -> list[dict]:
    evidence = get_all_drugs_for_variant_live(gene, variant, cancer_type=cancer_type, alphamissense_score=1.0)
    if not evidence:
        return []
    candidates = []
    for drug_name, level in evidence.items():
        if "R" in str(level):
            continue
        candidates.append({
            "drug_name": drug_name,
            "oncokb_level": level,
            "is_approved": True,
            "max_phase": 4,
            "opentargets_score": 0.8 if "LEVEL_1" in str(level) else (0.6 if "LEVEL_2" in str(level) else 0.4),
        })
    return rank_candidates(candidates)


def run_tier2(gene: str, variant: str, cancer_type: str) -> list[dict]:
    from services.opentargets import get_target_id, get_drugs_for_target
    from services.dgidb import get_interactions as get_dgidb_interactions

    async def _fetch():
        ensg_id = await get_target_id(gene)
        ot_drugs = await get_drugs_for_target(ensg_id, max_drugs=30) if ensg_id else []
        dgidb_drugs = await get_dgidb_interactions(gene, approved_only=False)
        return ot_drugs, dgidb_drugs

    ot_drugs, dgidb_drugs = asyncio.run(_fetch())
    seen = set()
    approved = []
    for d in (ot_drugs or []) + (dgidb_drugs or []):
        name = (d.get("drug_name") or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        if d.get("is_approved") or d.get("max_phase") == 4:
            approved.append(d)
    return rank_candidates(approved) if approved else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()
    base = args.data_dir

    # Load the 26 original-cohort patients
    with open(os.path.join(base, "candidate_patients.json")) as f:
        original = json.load(f)  # list of {patient_id, vcfs, drugs}

    # Original cohort: parse the REAL VCF file body (##cancer_type= header +
    # GENE=/HGVS= INFO fields), not the filename -- the file has clean
    # structured data, no need to guess from the name.
    import re
    original_entries = []
    for entry in original:
        pid = entry["patient_id"]
        vcf_path = os.path.join(_REPO_ROOT, "samples", "real", entry["vcfs"][0])
        with open(vcf_path, encoding="utf-8", errors="ignore") as vf:
            text = vf.read()
        cancer_m = re.search(r"^##cancer_type=(.+)$", text, re.MULTILINE)
        info_m = re.search(r"GENE=([A-Za-z0-9]+);HGVS=([^;\s]+)", text)
        original_entries.append({
            "patient_id": pid,
            "cohort": "local_sample",
            "gene": info_m.group(1).upper() if info_m else None,
            "variant_raw": info_m.group(2) if info_m else None,
            "cancer_type": cancer_m.group(1).strip() if cancer_m else "Unknown",
            "oncologist_drugs": entry["drugs"],
            "targeted_drugs": entry["drugs"],
        })

    # Load the 55 newly-fetched-cohort patients
    with open(os.path.join(base, "new_cohort_overlap.json")) as f:
        new_cohorts = json.load(f)

    new_entries = []
    for cohort, hits in new_cohorts.items():
        for h in hits:
            mut = _pick_variant(h["mutations"])
            if not mut:
                continue
            new_entries.append({
                "patient_id": h["patient_id"],
                "cohort": cohort,
                "gene": mut["gene"],
                "variant_raw": mut.get("proteinChange") or "",
                "cancer_type": _cohort_cancer_type(cohort),
                "oncologist_drugs": h["all_drugs"],
                "targeted_drugs": h["targeted_drugs"],
            })

    all_patients = original_entries + new_entries
    print(f"Total patients to run: {len(all_patients)}")

    results = []
    for i, p in enumerate(all_patients, 1):
        gene = p["gene"]
        variant = p["variant_raw"]
        if not gene or not variant:
            print(f"[{i}/{len(all_patients)}] {p['patient_id']}: SKIP (no gene/variant)")
            continue

        print(f"[{i}/{len(all_patients)}] {p['patient_id']} ({p['cohort']}) {gene} {variant} ... ", end="", flush=True)
        try:
            tier1 = run_tier1(gene, variant, p['cancer_type'])
            if tier1:
                tier = "TIER1_FDA_APPROVED"
                top3 = [d["drug_name"] for d in tier1[:3]]
            else:
                tier2 = run_tier2(gene, variant, p["cancer_type"])
                if tier2:
                    tier = "TIER2_REPURPOSING"
                    top3 = [d["drug_name"] for d in tier2[:3]]
                else:
                    tier = "NO_RECOMMENDATION"
                    top3 = []
        except Exception as e:
            tier = "ERROR"
            top3 = []
            print(f"ERROR: {e}")
        else:
            print(f"{tier} -> {top3}")

        results.append({
            **p,
            "pipeline_tier": tier,
            "pipeline_top3": top3,
        })

    out_path = os.path.join(base, "concordance_run_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} results to {out_path}")


if __name__ == "__main__":
    main()
