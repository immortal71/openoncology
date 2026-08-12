"""
Is the low concordance number a DATA problem or an ALGORITHM problem?

This script answers that using only the answer key itself -- it never looks at
what OpenOncology recommended. That matters: any diagnostic that consults our
own output to decide which patients "count" is circular (that is exactly how
scripts/build_concordance_labels.py produced its 100% number -- it derived each
patient's gene FROM the drug they were given, so a match was guaranteed).

The test here is instead:

    For a given cancer cohort, was the drug choice driven by the patient's
    sequenced gene, or by the cancer type?

If a drug is prescribed across many DIFFERENT genes within one cohort, then that
gene was not what selected the drug -- the cancer type was. A gene-targeted-
therapy engine cannot reproduce that prescribing pattern by design, and should
not be scored as if it could.
"""
import json
import os
import re
from collections import defaultdict, Counter

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def norm(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(
        r"\s+(mesylate|hydrochloride|dimaleate|maleate|acetate|tosylate|sodium"
        r"|disodium|malate|anhydrous|micronized|citrate|sulfate|phosphate)$",
        "", n)
    return n.strip()


def main():
    with open(os.path.join(_REPO_ROOT, "validation_results",
                           "real_patient_concordance_pilot_2026-07-28.json")) as f:
        patients = json.load(f)

    # drug -> cohort -> set(genes it was prescribed alongside)
    drug_genes = defaultdict(lambda: defaultdict(set))
    drug_patients = defaultdict(lambda: defaultdict(set))
    cohort_n = Counter()

    for p in patients:
        cohort = p["cohort"]
        gene = (p.get("gene") or "?").upper()
        cohort_n[cohort] += 1
        for d in set(norm(x) for x in (p.get("oncologist_drugs") or [])):
            drug_genes[d][cohort].add(gene)
            drug_patients[d][cohort].add(p["patient_id"])

    print("=" * 74)
    print("DATASET DIAGNOSIS - was prescribing gene-driven or cancer-type-driven?")
    print("2026-07-28 concordance pilot, n=%d patients" % len(patients))
    print("=" * 74)
    print()
    print("Cohort sizes:")
    for c, k in cohort_n.most_common():
        print("   %-16s %3d patients" % (c, k))
    print()

    print("-" * 74)
    print("DRUGS GIVEN TO 3+ PATIENTS, and how many DISTINCT genes they span")
    print("-" * 74)
    print("%-24s %-14s %6s %6s   %s" % ("drug", "cohort", "pts", "genes", "verdict"))
    print("-" * 74)

    type_driven = 0
    gene_driven = 0
    rows = []
    for drug in drug_genes:
        for cohort, genes in drug_genes[drug].items():
            npat = len(drug_patients[drug][cohort])
            if npat < 3:
                continue
            ngene = len(genes)
            # Given to many patients spanning many genes => the gene did not
            # select the drug; the cancer type did.
            verdict = "CANCER-TYPE-DRIVEN" if ngene >= 3 else "possibly gene-linked"
            if ngene >= 3:
                type_driven += npat
            else:
                gene_driven += npat
            rows.append((npat, drug, cohort, ngene, verdict, sorted(genes)))

    for npat, drug, cohort, ngene, verdict, genes in sorted(rows, reverse=True):
        print("%-24s %-14s %6d %6d   %s" % (drug[:24], cohort[:14], npat, ngene, verdict))

    print()
    print("-" * 74)
    print("WORKED EXAMPLE - the single clearest case")
    print("-" * 74)
    top = max(rows, key=lambda r: r[0])
    npat, drug, cohort, ngene, verdict, genes = top
    print("'%s' was given to %d patients in %s," % (drug, npat, cohort))
    print("spanning %d different sequenced genes:" % ngene)
    print("   %s" % ", ".join(genes))
    print()
    print("Those patients did not share a gene. They shared a diagnosis.")
    print("A gene-to-drug engine is being asked to output '%s' for" % drug)
    print("%d unrelated genes -- which would require ignoring the gene entirely." % ngene)
    print()

    # Per-cohort: how concentrated is prescribing?
    print("-" * 74)
    print("PRESCRIBING CONCENTRATION PER COHORT")
    print("(if a handful of drugs cover most patients, it is protocol care)")
    print("-" * 74)
    for cohort in cohort_n:
        counts = Counter()
        for p in patients:
            if p["cohort"] != cohort:
                continue
            for d in set(norm(x) for x in (p.get("oncologist_drugs") or [])):
                counts[d] += 1
        n = cohort_n[cohort]
        top5 = counts.most_common(5)
        covered = set()
        for p in patients:
            if p["cohort"] != cohort:
                continue
            pd = set(norm(x) for x in (p.get("oncologist_drugs") or []))
            if pd & {d for d, _ in top5}:
                covered.add(p["patient_id"])
        print()
        print("  %s (n=%d): top-5 drugs reach %d/%d patients (%.0f%%)"
              % (cohort, n, len(covered), n, 100.0 * len(covered) / n))
        for d, k in top5:
            print("      %-28s %2d patients" % (d, k))


if __name__ == "__main__":
    main()
