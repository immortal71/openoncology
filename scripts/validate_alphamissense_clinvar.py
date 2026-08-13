"""Analytical validation gate: AlphaMissense agreement with ClinVar on BRCA1/2.

WHAT THIS MEASURES
------------------
docs/REGULATORY_FRAMEWORK.md section 3.1 lists "AlphaMissense score concordance
with ClinVar pathogenicity, target >= 90% on BRCA1/2 benchmarks" as an unmet
analytical validation gate. This script measures it.

Two independent public sources, joined on the protein variant and nothing else:

  prediction <- AlphaMissense pre-computed scores (Cheng et al., Science 2023;
                doi:10.1126/science.adg7492), Zenodo record 8208688, file
                AlphaMissense_aa_substitutions.tsv.gz
  truth      <- ClinVar variant_summary.txt.gz from NCBI, the archive's own
                ClinicalSignificance and ReviewStatus fields

Neither derives the other. AlphaMissense was trained without ClinVar labels for
these variants and ClinVar assertions are submitted by clinical laboratories.

READ THE CLASS BALANCE BEFORE READING THE HEADLINE
--------------------------------------------------
BRCA1 and BRCA2 act through loss of function, so most pathogenic ClinVar entries
are truncating (frameshift, nonsense, splice). AlphaMissense scores missense
substitutions only, so those variants are out of scope by construction and the
surviving pathogenic set is small. A raw agreement percentage on an imbalanced
set can be high while the classifier is useless on the minority class, which is
the class that matters clinically.

So this reports sensitivity and specificity separately, and balanced accuracy,
alongside raw agreement. Quote the balanced figure, not the raw one.

AlphaMissense's own three-way call is used as published: likely_pathogenic,
likely_benign, and ambiguous. Ambiguous is a real answer, not a miss, so it is
reported as its own column rather than silently counted either way. The strict
reading treats ambiguous as non-concordant; the restricted reading excludes it.
Both are printed, because choosing one silently is how a benchmark flatters
itself.

Usage:
    python scripts/validate_alphamissense_clinvar.py            # fetch + measure
    python scripts/validate_alphamissense_clinvar.py --offline  # reuse extracts
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import sys
import urllib.request
from collections import Counter

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CACHE_DIR = os.path.join(_REPO_ROOT, "validation_results", "cache")
_RESULTS_OUT = os.path.join(_REPO_ROOT, "validation_results", "alphamissense_clinvar_concordance.json")

# Small filtered extracts, kept so --offline reruns need no network.
_CLINVAR_EXTRACT = os.path.join(_CACHE_DIR, "clinvar_brca_missense.tsv")
_AM_EXTRACT = os.path.join(_CACHE_DIR, "alphamissense_brca.tsv")

CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
ALPHAMISSENSE_URL = (
    "https://zenodo.org/records/8208688/files/"
    "AlphaMissense_aa_substitutions.tsv.gz?download=1"
)

# UniProt accessions for the canonical BRCA1 and BRCA2 proteins. AlphaMissense
# keys its amino-acid substitution file on these.
UNIPROT = {"P38398": "BRCA1", "P51587": "BRCA2"}
GENES = {"BRCA1", "BRCA2"}

# ClinVar assertions that constitute a usable label. Conflicting and
# uncertain-significance entries are excluded because they are not a truth
# value; they are recorded in the attrition counts instead.
PATHOGENIC_ASSERTIONS = {"pathogenic", "likely pathogenic", "pathogenic/likely pathogenic"}
BENIGN_ASSERTIONS = {"benign", "likely benign", "benign/likely benign"}

# ClinVar review status, ordered. "criteria provided" is the floor for the
# headline; expert panel and practice guideline are reported separately.
_REVIEW_RANK = {
    "no assertion provided": 0,
    "no classification provided": 0,
    "no assertion criteria provided": 0,
    "no classification for the single variant": 0,
    "criteria provided, single submitter": 1,
    "criteria provided, conflicting classifications": 1,
    "criteria provided, conflicting interpretations": 1,
    "criteria provided, multiple submitters": 2,
    "criteria provided, multiple submitters, no conflicts": 2,
    "reviewed by expert panel": 3,
    "practice guideline": 4,
}

# AlphaMissense thresholds, as published in the paper and used by
# ai/alphamissense/classify.py.
PATHOGENIC_THRESHOLD = 0.564
BENIGN_THRESHOLD = 0.340

# Three-letter to one-letter amino acid codes. Sequence notation, not a
# clinical judgement.
_AA3_TO_1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q",
    "Glu": "E", "Gly": "G", "His": "H", "Ile": "I", "Leu": "L", "Lys": "K",
    "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W",
    "Tyr": "Y", "Val": "V",
}

# p.Arg1699Gln -> R1699Q. Deliberately refuses Ter/fs/del/dup/ext: those are not
# missense and AlphaMissense does not score them.
_PROTEIN_RE = re.compile(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})\)?\s*$")


def _download(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "openoncology-research"})
    with urllib.request.urlopen(req, timeout=600) as response, open(dest, "wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
            done += len(chunk)
            if total:
                pct = 100.0 * done / total
                print(f"\r  {done/1e6:7.1f} / {total/1e6:.1f} MB ({pct:5.1f}%)", end="", flush=True)
    print()


def _parse_protein_change(name: str) -> str | None:
    """Pull the missense substitution out of a ClinVar Name field."""
    match = _PROTEIN_RE.search(name or "")
    if not match:
        return None
    ref3, pos, alt3 = match.group(1), match.group(2), match.group(3)
    ref = _AA3_TO_1.get(ref3)
    alt = _AA3_TO_1.get(alt3)
    if not ref or not alt or ref == alt:
        return None
    return f"{ref}{pos}{alt}"


def extract_clinvar(source_gz: str, out_tsv: str) -> dict[str, int]:
    """Stream variant_summary.txt.gz, keep BRCA1/2 missense rows with a label."""
    stats: Counter = Counter()
    os.makedirs(os.path.dirname(out_tsv), exist_ok=True)

    with gzip.open(source_gz, "rt", encoding="utf-8", errors="replace") as handle, \
            open(out_tsv, "w", encoding="utf-8", newline="") as out:
        reader = csv.DictReader(handle, delimiter="\t")
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "protein_change", "label", "assertion", "review_status", "variation_id"])

        for row in reader:
            gene = (row.get("GeneSymbol") or "").strip().upper()
            if gene not in GENES:
                continue
            # variant_summary carries one row per assembly; take GRCh38 only so
            # a variant is not counted twice.
            if (row.get("Assembly") or "").strip() != "GRCh38":
                continue
            stats["brca_rows_grch38"] += 1

            protein_change = _parse_protein_change(row.get("Name") or "")
            if not protein_change:
                stats["not_a_simple_missense"] += 1
                continue
            stats["missense"] += 1

            assertion = (row.get("ClinicalSignificance") or "").strip().lower()
            if assertion in PATHOGENIC_ASSERTIONS:
                label = "pathogenic"
            elif assertion in BENIGN_ASSERTIONS:
                label = "benign"
            else:
                stats["no_usable_label"] += 1
                continue

            stats[f"labelled_{label}"] += 1
            writer.writerow([
                gene,
                protein_change,
                label,
                assertion,
                (row.get("ReviewStatus") or "").strip().lower(),
                (row.get("VariationID") or "").strip(),
            ])

    return dict(stats)


def extract_alphamissense(source_gz: str, out_tsv: str) -> dict[str, int]:
    """Stream the 1.2 GB substitution file, keep only the two BRCA accessions."""
    stats: Counter = Counter()
    os.makedirs(os.path.dirname(out_tsv), exist_ok=True)

    with gzip.open(source_gz, "rt", encoding="utf-8", errors="replace") as handle, \
            open(out_tsv, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "protein_change", "am_pathogenicity", "am_class"])

        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            uniprot = parts[0]
            gene = UNIPROT.get(uniprot)
            if not gene:
                continue
            stats[f"rows_{gene}"] += 1
            writer.writerow([gene, parts[1], parts[2], parts[3]])

    return dict(stats)


def _load_tsv(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _am_call(score: float) -> str:
    if score >= PATHOGENIC_THRESHOLD:
        return "pathogenic"
    if score <= BENIGN_THRESHOLD:
        return "benign"
    return "ambiguous"


def _metrics(pairs: list[tuple[str, str]]) -> dict:
    """pairs of (clinvar_label, alphamissense_call)."""
    tp = sum(1 for t, p in pairs if t == "pathogenic" and p == "pathogenic")
    tn = sum(1 for t, p in pairs if t == "benign" and p == "benign")
    fp = sum(1 for t, p in pairs if t == "benign" and p == "pathogenic")
    fn = sum(1 for t, p in pairs if t == "pathogenic" and p == "benign")
    amb_path = sum(1 for t, p in pairs if t == "pathogenic" and p == "ambiguous")
    amb_ben = sum(1 for t, p in pairs if t == "benign" and p == "ambiguous")

    n_path = tp + fn + amb_path
    n_ben = tn + fp + amb_ben
    n_all = n_path + n_ben
    n_called = tp + tn + fp + fn

    sensitivity = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    balanced = (
        (sensitivity + specificity) / 2
        if sensitivity is not None and specificity is not None
        else None
    )

    return {
        "n_variants": n_all,
        "n_pathogenic": n_path,
        "n_benign": n_ben,
        "n_with_a_definite_call": n_called,
        "n_ambiguous": amb_path + amb_ben,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "ambiguous_on_pathogenic": amb_path,
        "ambiguous_on_benign": amb_ben,
        "agreement_strict_pct": round(100.0 * (tp + tn) / n_all, 2) if n_all else None,
        "agreement_excluding_ambiguous_pct": round(100.0 * (tp + tn) / n_called, 2) if n_called else None,
        "sensitivity_pct": round(100.0 * sensitivity, 2) if sensitivity is not None else None,
        "specificity_pct": round(100.0 * specificity, 2) if specificity is not None else None,
        "balanced_accuracy_pct": round(100.0 * balanced, 2) if balanced is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse the cached extracts")
    parser.add_argument("--keep-downloads", action="store_true",
                        help="keep the multi-GB source archives after extracting")
    args = parser.parse_args()

    if not args.offline or not (os.path.exists(_CLINVAR_EXTRACT) and os.path.exists(_AM_EXTRACT)):
        clinvar_gz = os.path.join(_CACHE_DIR, "variant_summary.txt.gz")
        am_gz = os.path.join(_CACHE_DIR, "AlphaMissense_aa_substitutions.tsv.gz")

        if not os.path.exists(clinvar_gz):
            print(f"Downloading ClinVar variant_summary ({CLINVAR_URL})")
            _download(CLINVAR_URL, clinvar_gz)
        print("Extracting BRCA1/2 missense rows with a usable label...")
        cv_stats = extract_clinvar(clinvar_gz, _CLINVAR_EXTRACT)
        print(f"  {cv_stats}")

        if not os.path.exists(am_gz):
            print(f"Downloading AlphaMissense substitutions ({ALPHAMISSENSE_URL})")
            _download(ALPHAMISSENSE_URL, am_gz)
        print("Extracting BRCA1/2 rows...")
        am_stats = extract_alphamissense(am_gz, _AM_EXTRACT)
        print(f"  {am_stats}")

        if not args.keep_downloads:
            for path in (clinvar_gz, am_gz):
                if os.path.exists(path):
                    os.remove(path)
            print("  removed the source archives (pass --keep-downloads to retain)")

    clinvar_rows = _load_tsv(_CLINVAR_EXTRACT)
    am_rows = _load_tsv(_AM_EXTRACT)

    am_index: dict[tuple[str, str], float] = {}
    for row in am_rows:
        try:
            am_index[(row["gene"], row["protein_change"])] = float(row["am_pathogenicity"])
        except (KeyError, ValueError):
            continue

    # One row per variant. ClinVar can carry several rows for the same protein
    # change; keep the one with the strongest review status.
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in clinvar_rows:
        key = (row["gene"], row["protein_change"])
        rank = _REVIEW_RANK.get(row["review_status"], 0)
        current = best.get(key)
        if current is None or rank > _REVIEW_RANK.get(current["review_status"], 0):
            best[key] = row

    matched: list[dict] = []
    unmatched = 0
    for key, row in sorted(best.items()):
        score = am_index.get(key)
        if score is None:
            unmatched += 1
            continue
        matched.append({
            "gene": key[0],
            "protein_change": key[1],
            "clinvar_label": row["label"],
            "clinvar_assertion": row["assertion"],
            "review_status": row["review_status"],
            "review_rank": _REVIEW_RANK.get(row["review_status"], 0),
            "variation_id": row["variation_id"],
            "am_pathogenicity": score,
            "am_call": _am_call(score),
        })

    def _pairs(rows: list[dict]) -> list[tuple[str, str]]:
        return [(r["clinvar_label"], r["am_call"]) for r in rows]

    criteria = [r for r in matched if r["review_rank"] >= 1]
    expert = [r for r in matched if r["review_rank"] >= 3]

    overall = _metrics(_pairs(criteria))
    expert_metrics = _metrics(_pairs(expert)) if expert else None
    by_gene = {
        gene: _metrics(_pairs([r for r in criteria if r["gene"] == gene]))
        for gene in sorted(GENES)
    }

    target_pct = 90.0
    headline = overall["balanced_accuracy_pct"]

    print()
    print("=" * 74)
    print("ALPHAMISSENSE vs CLINVAR  (BRCA1 / BRCA2 missense)")
    print("=" * 74)
    print(f"  ClinVar rows extracted        : {len(clinvar_rows)}")
    print(f"  unique labelled variants      : {len(best)}")
    print(f"  no AlphaMissense score        : {unmatched}")
    print(f"  scored, criteria provided     : {len(criteria)}")
    print(f"    pathogenic / benign         : {overall['n_pathogenic']} / {overall['n_benign']}")
    print()
    print(f"  agreement, ambiguous counted as wrong : {overall['agreement_strict_pct']}%")
    print(f"  agreement, ambiguous excluded         : {overall['agreement_excluding_ambiguous_pct']}%")
    print(f"  sensitivity (pathogenic recall)       : {overall['sensitivity_pct']}%")
    print(f"  specificity (benign recall)           : {overall['specificity_pct']}%")
    print(f"  BALANCED ACCURACY                     : {headline}%")
    print(f"  ambiguous calls                       : {overall['n_ambiguous']}")
    print()
    for gene, m in by_gene.items():
        print(f"  {gene}: n={m['n_variants']} (P {m['n_pathogenic']} / B {m['n_benign']}), "
              f"balanced {m['balanced_accuracy_pct']}%")
    if expert_metrics:
        print()
        print(f"  expert panel / practice guideline only: n={expert_metrics['n_variants']}, "
              f"balanced {expert_metrics['balanced_accuracy_pct']}%")
    print()

    passed = headline is not None and headline >= target_pct
    print("=" * 74)
    print(f"  GATE (REGULATORY_FRAMEWORK.md 3.1): balanced accuracy >= {target_pct}%")
    print(f"  RESULT: {headline}%  ->  {'PASS' if passed else 'FAIL'}")
    print()
    print("  Read with the class balance in mind. BRCA1/2 act through loss of")
    print("  function, so most pathogenic ClinVar entries are truncating and are")
    print("  out of scope for a missense predictor. Raw agreement on the")
    print("  surviving set is dominated by whichever class is larger, which is")
    print("  why the balanced figure is the one gated on.")
    print("=" * 74)

    payload = {
        "gate": "alphamissense_clinvar_concordance_brca",
        "target": {"metric": "balanced_accuracy_pct", "threshold": target_pct},
        "result": {"balanced_accuracy_pct": headline, "passed": bool(passed)},
        "sources": {
            "prediction": "AlphaMissense (Cheng et al., Science 2023, doi:10.1126/science.adg7492), "
                          "Zenodo 8208688, AlphaMissense_aa_substitutions.tsv.gz",
            "truth": "NCBI ClinVar variant_summary.txt.gz",
            "join": "protein variant only; neither source derives the other",
        },
        "thresholds": {
            "alphamissense_pathogenic": PATHOGENIC_THRESHOLD,
            "alphamissense_benign": BENIGN_THRESHOLD,
        },
        "attrition": {
            "unique_labelled_clinvar_variants": len(best),
            "without_an_alphamissense_score": unmatched,
            "scored_with_criteria_provided": len(criteria),
        },
        "metrics_overall": overall,
        "metrics_by_gene": by_gene,
        "metrics_expert_panel_only": expert_metrics,
        "variants": matched,
    }
    os.makedirs(os.path.dirname(_RESULTS_OUT), exist_ok=True)
    with open(_RESULTS_OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {os.path.relpath(_RESULTS_OUT, _REPO_ROOT)}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
