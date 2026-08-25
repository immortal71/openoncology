"""Does the pipeline's recommendation predict measured drug sensitivity?

WHY THIS ONE IS DIFFERENT
-------------------------
Every other benchmark in this repository compares the pipeline against a
knowledge base. NCI-MATCH arms, OncoKB levels and the gold cases in
api/services/benchmark.py are all expert curation of the same published
actionability literature this repo's evidence table is built from, so agreement
partly measures whether we encoded the literature correctly. The oncologist
concordance benchmark avoids that but scores against protocol-era chemotherapy,
which was not biomarker-driven at all.

This one uses a wet-lab measurement as the answer key.

  input   <- real mutation profiles of cancer cell lines, cBioPortal CCLE
             (Broad, 2019)
  output  <- what this pipeline recommends for those mutations
  truth   <- measured dose-response for those exact cell lines, GDSC2
             (Genomics of Drug Sensitivity in Cancer, Sanger)

Nothing links the three except the cell line's own mutations. GDSC IC50 values
were measured in a laboratory years before this repository existed and are not
derived from OncoKB, CIViC, or any actionability database.

THE METRIC
----------
GDSC publishes Z_SCORE: the cell line's sensitivity to a drug, standardised
across all cell lines tested with that same drug. So it already controls for
the fact that some drugs are potent everywhere.

  Z_SCORE < 0  this cell line is MORE sensitive to this drug than average
  Z_SCORE = 0  no different from the average cell line
  Z_SCORE > 0  less sensitive than average

The question is therefore sharp and has a real null hypothesis: when the
pipeline recommends drug D for cell line C because of C's mutations, is C
measurably more sensitive to D than other cell lines are?

  H0: recommended pairs have the same Z_SCORE distribution as unrecommended
      pairs in the same cell lines. The pipeline carries no information about
      real drug response.
  H1: recommended pairs are shifted negative.

Tested by permutation, so no distributional assumption is made. The control
group is drugs tested on the SAME cell lines but not recommended for them,
which holds cell line identity fixed.

WHAT IT STILL CANNOT SHOW
-------------------------
Cell lines are not patients. Sensitivity in culture is a poor predictor of
clinical response for many drug classes, immunotherapy above all, since there
is no immune system in a dish. A positive result here means the biomarker to
drug links being asserted have measurable biological reality, not that a
patient would benefit. That is a genuinely different claim and this script does
not make it.

Usage:
    python scripts/validate_cell_line_drug_response.py
    python scripts/validate_cell_line_drug_response.py --offline
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import re
import statistics
import sys
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "cell-line-validation-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

_CACHE_DIR = os.path.join(_REPO_ROOT, "validation_results", "cache")
_GDSC_EXTRACT = os.path.join(_CACHE_DIR, "gdsc2_response.tsv")
_CCLE_EXTRACT = os.path.join(_CACHE_DIR, "ccle_mutations.tsv")
_RESULTS_OUT = os.path.join(_REPO_ROOT, "validation_results", "cell_line_drug_response.json")

GDSC_URL = (
    "https://ftp.sanger.ac.uk/pub/project/cancerrxgene/releases/current_release/"
    "GDSC2_fitted_dose_response_24Jul22.csv"
)
CBIO = "https://www.cbioportal.org/api"
CCLE_STUDY = "ccle_broad_2019"
GENE_PANEL_ID = "IMPACT468"

# A cell line needs enough drugs tested on it for a within-line control to mean
# anything.
_MIN_DRUGS_PER_LINE = 20
_PERMUTATIONS = 20000
_SEED = 20260813


def _norm_drug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _norm_cell_line(name: str) -> str:
    """CCLE writes A549_LUNG, GDSC writes A-549. Both reduce to A549."""
    base = (name or "").upper()
    # CCLE appends the tissue after the first underscore.
    base = base.split("_")[0]
    return re.sub(r"[^A-Z0-9]+", "", base)


def _get(url: str, timeout: int = 120):
    req = urllib.request.Request(url, headers={"User-Agent": "openoncology-research", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _post(url: str, body: dict, timeout: int = 300):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "User-Agent": "openoncology-research",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(url=req, timeout=timeout) as response:
        return json.load(response)


def fetch_ccle_mutations() -> None:
    panel = _get(f"{CBIO}/gene-panels/{GENE_PANEL_ID}")
    entrez = sorted({g["entrezGeneId"] for g in panel["genes"]})
    print(f"  panel {GENE_PANEL_ID}: {len(entrez)} genes")

    records = _post(
        f"{CBIO}/molecular-profiles/{CCLE_STUDY}_mutations/mutations/fetch?projection=DETAILED",
        {"sampleListId": f"{CCLE_STUDY}_all", "entrezGeneIds": entrez},
    )
    print(f"  {len(records)} panel mutations across CCLE")

    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_CCLE_EXTRACT, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["cell_line", "gene", "protein_change", "mutation_type"])
        for record in records:
            protein_change = (record.get("proteinChange") or "").strip()
            gene = (record.get("gene") or {}).get("hugoGeneSymbol")
            sample = record.get("sampleId") or ""
            if not protein_change or not gene or not sample:
                continue
            writer.writerow([sample, gene, protein_change, record.get("mutationType") or ""])


def fetch_gdsc() -> None:
    print(f"  downloading {GDSC_URL.rsplit('/', 1)[-1]} (~40 MB)")
    req = urllib.request.Request(GDSC_URL, headers={"User-Agent": "openoncology-research"})
    with urllib.request.urlopen(req, timeout=900) as response:
        raw = response.read()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
    print(f"  {len(rows)} dose-response curves")

    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_GDSC_EXTRACT, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["cell_line", "drug", "ln_ic50", "auc", "z_score"])
        for row in rows:
            try:
                writer.writerow([
                    row["CELL_LINE_NAME"], row["DRUG_NAME"],
                    row["LN_IC50"], row["AUC"], row["Z_SCORE"],
                ])
            except KeyError:
                continue


def _load(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def recommend(gene: str, variant: str) -> list[str]:
    """Top-3 from the production Tier 1 path, same as the other benchmarks."""
    from ai.ranking import rank_candidates
    from services.oncokb_evidence import get_all_drugs_for_variant

    evidence = get_all_drugs_for_variant(gene, variant, alphamissense_score=1.0) or {}
    candidates = []
    for drug_name, level in evidence.items():
        level_text = str(level)
        if "R" in level_text:  # resistance markers are not recommendations
            continue
        candidates.append({
            "drug_name": drug_name,
            "oncokb_level": level,
            "is_approved": True,
            "max_phase": 4,
            "opentargets_score": 0.8 if "LEVEL_1" in level_text else (
                0.6 if "LEVEL_2" in level_text else 0.4),
        })
    if not candidates:
        return []
    return [c["drug_name"] for c in rank_candidates(candidates)[:3]]


def _permutation_p(recommended: list[float], control: list[float], rng: random.Random) -> float:
    """One-sided: are recommended pairs shifted more sensitive than control?"""
    observed = statistics.mean(recommended) - statistics.mean(control)
    pooled = recommended + control
    n = len(recommended)
    hits = 0
    for _ in range(_PERMUTATIONS):
        rng.shuffle(pooled)
        diff = statistics.mean(pooled[:n]) - statistics.mean(pooled[n:])
        if diff <= observed:
            hits += 1
    return (hits + 1) / (_PERMUTATIONS + 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse cached extracts")
    args = parser.parse_args()

    if not args.offline or not os.path.exists(_CCLE_EXTRACT):
        print("Fetching CCLE mutations...")
        fetch_ccle_mutations()
    if not args.offline or not os.path.exists(_GDSC_EXTRACT):
        print("Fetching GDSC2 dose response...")
        fetch_gdsc()

    # cell line -> [(gene, variant)]
    mutations: dict[str, list[tuple[str, str]]] = {}
    for row in _load(_CCLE_EXTRACT):
        key = _norm_cell_line(row["cell_line"])
        if key:
            mutations.setdefault(key, []).append((row["gene"], row["protein_change"]))

    # cell line -> {drug -> z_score}
    response: dict[str, dict[str, float]] = {}
    for row in _load(_GDSC_EXTRACT):
        key = _norm_cell_line(row["cell_line"])
        try:
            z = float(row["z_score"])
        except (TypeError, ValueError):
            continue
        if key:
            response.setdefault(key, {})[_norm_drug(row["drug"])] = z

    shared = sorted(set(mutations) & set(response))
    scored_lines = [c for c in shared if len(response[c]) >= _MIN_DRUGS_PER_LINE]

    rec_z: list[float] = []
    ctl_z: list[float] = []
    per_line: list[dict] = []
    cache: dict[tuple[str, str], list[str]] = {}

    for line in scored_lines:
        recommended: set[str] = set()
        for gene, variant in mutations[line]:
            key = (gene, variant)
            if key not in cache:
                cache[key] = recommend(gene, variant)
            recommended.update(_norm_drug(d) for d in cache[key])

        tested = response[line]
        hits = sorted(recommended & set(tested))
        if not hits:
            continue

        line_rec = [tested[d] for d in hits]
        line_ctl = [z for d, z in tested.items() if d not in recommended]
        if not line_ctl:
            continue

        rec_z.extend(line_rec)
        ctl_z.extend(line_ctl)
        per_line.append({
            "cell_line": line,
            "n_mutations": len(mutations[line]),
            "n_drugs_tested": len(tested),
            "recommended_and_tested": hits,
            "mean_z_recommended": round(statistics.mean(line_rec), 4),
            "mean_z_control": round(statistics.mean(line_ctl), 4),
        })

    print()
    print("=" * 78)
    print("CELL LINE DRUG RESPONSE  (pipeline recommendation vs measured GDSC2 IC50)")
    print("=" * 78)
    print(f"  CCLE cell lines with panel mutations   : {len(mutations)}")
    print(f"  GDSC2 cell lines with response data    : {len(response)}")
    print(f"  present in both                        : {len(shared)}")
    print(f"  with >= {_MIN_DRUGS_PER_LINE} drugs tested                : {len(scored_lines)}")
    print(f"  SCORED (pipeline named a tested drug)  : {len(per_line)}")
    print()

    if not rec_z or not ctl_z:
        print("  No scorable pairs. Nothing can be concluded.")
        return 1

    mean_rec = statistics.mean(rec_z)
    mean_ctl = statistics.mean(ctl_z)
    pooled_sd = statistics.pstdev(rec_z + ctl_z) or 1.0
    effect = (mean_rec - mean_ctl) / pooled_sd
    rng = random.Random(_SEED)
    p_value = _permutation_p(list(rec_z), list(ctl_z), rng)

    print(f"  recommended drug/cell-line pairs       : {len(rec_z)}")
    print(f"  control pairs (same lines, not rec'd)  : {len(ctl_z)}")
    print()
    print(f"  mean Z_SCORE, recommended              : {mean_rec:+.4f}")
    print(f"  mean Z_SCORE, control                  : {mean_ctl:+.4f}")
    print(f"  difference                             : {mean_rec - mean_ctl:+.4f}")
    print(f"  effect size (Cohen's d)                : {effect:+.3f}")
    print(f"  permutation p (one-sided, {_PERMUTATIONS} shuffles) : {p_value:.5f}")
    print()
    print("  Negative Z_SCORE means the cell line is MORE sensitive to the drug")
    print("  than the average cell line tested with it.")
    print()

    significant = p_value < 0.05 and mean_rec < mean_ctl
    print("=" * 78)
    if significant:
        print("  RESULT: recommended drugs are measurably more effective on the")
        print("          cell lines they were recommended for.")
    else:
        print("  RESULT: no detectable shift. On this evidence the recommendation")
        print("          carries no information about measured drug response.")
    print()
    print("  Cell lines are not patients. Sensitivity in culture predicts clinical")
    print("  response poorly for many drug classes, immunotherapy most of all,")
    print("  since there is no immune system in a dish. This speaks to whether the")
    print("  biomarker-to-drug links have measurable biological reality, not to")
    print("  whether a patient would benefit.")
    print("=" * 78)

    payload = {
        "benchmark": "cell_line_drug_response",
        "question": (
            "When the pipeline recommends drug D for cell line C on the basis of C's "
            "mutations, is C measurably more sensitive to D than other cell lines are?"
        ),
        "sources": {
            "mutations": f"cBioPortal {CCLE_STUDY} (Cancer Cell Line Encyclopedia, Broad 2019)",
            "truth": "GDSC2 fitted dose response, Genomics of Drug Sensitivity in Cancer (Sanger)",
            "independence": (
                "GDSC IC50 values are laboratory measurements and are not derived from "
                "OncoKB, CIViC or any actionability database."
            ),
        },
        "metric": "GDSC Z_SCORE, sensitivity standardised across cell lines per drug; negative is more sensitive",
        "denominator": {
            "ccle_lines_with_mutations": len(mutations),
            "gdsc_lines_with_response": len(response),
            "in_both": len(shared),
            "with_enough_drugs_tested": len(scored_lines),
            "scored": len(per_line),
        },
        "result": {
            "n_recommended_pairs": len(rec_z),
            "n_control_pairs": len(ctl_z),
            "mean_z_recommended": round(mean_rec, 4),
            "mean_z_control": round(mean_ctl, 4),
            "difference": round(mean_rec - mean_ctl, 4),
            "cohens_d": round(effect, 4),
            "permutation_p_one_sided": round(p_value, 5),
            "significant": bool(significant),
        },
        "limitation": (
            "Cell lines are not patients. In-culture sensitivity predicts clinical response "
            "poorly for many drug classes, immunotherapy especially. A positive result means "
            "the asserted biomarker-to-drug links have measurable biological reality, not that "
            "a patient would benefit."
        ),
        "per_cell_line": per_line,
    }
    os.makedirs(os.path.dirname(_RESULTS_OUT), exist_ok=True)
    with open(_RESULTS_OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {os.path.relpath(_RESULTS_OUT, _REPO_ROOT)}")

    return 0 if significant else 1


if __name__ == "__main__":
    sys.exit(main())
