"""Detect whether a concordance label set is circular.

THE DEFECT THIS MEASURES
------------------------
scripts/build_concordance_labels.py used to derive the biomarker from the drug
via DRUG_BIOMARKER_MAP, so every trastuzumab patient was labelled "ERBB2
Amplified" whether or not they were ever sequenced. A benchmark scored against
labels built that way cannot produce any answer except a high one, because the
answer was written into the question.

That map is gone and the builder now joins two independent sources, so this
check passes on the current labels. It stays because the defect is easy to
reintroduce and impossible to see in the reported number.

That is invisible in the reported number. 100% concordance looks like success,
not like a tautology, which is exactly why it needs a test rather than a
comment.

HOW IT DETECTS IT
-----------------
Measured labels and derived labels have different statistical signatures.

If a clinician chose a drug for a real patient, patients on that drug carry a
spread of genes: some have the matching biomarker, some do not, because
prescribing depends on more than one marker. If instead the gene was computed
from the drug, then every patient on drug X has gene Y with no exceptions.

So the test is conditional entropy. For each drug, look at the distribution of
genes among patients receiving it. Zero entropy across the board, meaning drug
perfectly predicts gene, is the fingerprint of derivation. Real clinical data
is never that clean.

This asserts nothing about what concordance should be. It only answers whether
the labels can support the claim at all.

Exit code is 1 when circularity is detected, so this can gate CI.

Usage:
    python scripts/detect_label_circularity.py
    python scripts/detect_label_circularity.py --labels path/to/labels.json
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT = os.path.join(_REPO_ROOT, "scripts", "concordance_labels.json")

# A drug seen fewer times than this says nothing either way, since a single
# patient trivially has zero entropy.
_MIN_SUPPORT = 5


def _load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        for key in ("labels", "cases", "records"):
            if key in payload:
                return payload[key]
    return payload


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    out = 0.0
    for n in counts:
        if n <= 0:
            continue
        p = n / total
        out -= p * math.log2(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=_DEFAULT)
    args = parser.parse_args()

    rows = _load(args.labels)

    # gene distribution per drug
    per_drug: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    genes_present = 0
    for row in rows:
        gene = (row.get("gene") or "").strip().upper()
        drugs = row.get("oncologist_recommended_drugs") or []
        if gene:
            genes_present += 1
        for drug in drugs:
            key = str(drug).strip().lower()
            if key:
                per_drug[key][gene or "<none>"] += 1

    print("=" * 74)
    print("CONCORDANCE LABEL CIRCULARITY CHECK")
    print("=" * 74)
    print(f"  labels file      : {os.path.relpath(args.labels, _REPO_ROOT)}")
    print(f"  records          : {len(rows)}")
    print(f"  with a gene      : {genes_present} ({100.0 * genes_present / max(1, len(rows)):.1f}%)")
    print(f"  distinct drugs   : {len(per_drug)}")
    print()

    scored = [(d, c) for d, c in per_drug.items() if sum(c.values()) >= _MIN_SUPPORT]
    if not scored:
        print("  not enough drug support to judge")
        return 0

    deterministic, informative = [], []
    for drug, counter in scored:
        real = collections.Counter({g: n for g, n in counter.items() if g != "<none>"})
        if not real:
            continue
        h = _entropy(list(real.values()))
        (deterministic if h == 0.0 else informative).append((drug, h, real))

    total_judged = len(deterministic) + len(informative)
    if not total_judged:
        print("  no drug has any gene attached; labels carry no biomarker at all")
        print()
        print("  VERDICT: unusable, not merely circular")
        return 1

    frac = len(deterministic) / total_judged
    print(f"  drugs with >= {_MIN_SUPPORT} labelled patients : {total_judged}")
    print(f"  drug perfectly predicts gene         : {len(deterministic)} ({100.0 * frac:.1f}%)")
    print(f"  drug leaves gene uncertain           : {len(informative)}")
    print()

    if deterministic:
        print("  deterministic drug to gene mappings (the fingerprint of derivation):")
        for drug, _h, real in sorted(deterministic, key=lambda t: -sum(t[2].values()))[:12]:
            gene = next(iter(real))
            print(f"    {drug:<28} -> {gene:<10} in all {sum(real.values())} patients")
        print()

    if informative:
        print("  drugs whose gene actually varies (what measured data looks like):")
        for drug, h, real in sorted(informative, key=lambda t: -t[1])[:6]:
            spread = ", ".join(f"{g}:{n}" for g, n in real.most_common(4))
            print(f"    {drug:<28} entropy={h:.2f}  {spread}")
        print()

    # The decisive test. Cytotoxic chemotherapy and supportive care are
    # prescribed without reference to any biomarker, so in measured data the
    # genes among patients receiving them must vary. If cisplatin perfectly
    # predicts EGFR, or zoledronic acid perfectly predicts ERBB2, the gene did
    # not come from the patient. It came from something else in the regimen and
    # was then attached to every co-administered drug.
    #
    # This catches derivation that the aggregate fraction misses: a label set
    # can sit below the entropy threshold overall and still be built this way.
    AGNOSTIC = {
        "cisplatin", "carboplatin", "oxaliplatin", "fluorouracil", "leucovorin",
        "cyclophosphamide", "doxorubicin", "epirubicin", "paclitaxel",
        "docetaxel", "gemcitabine", "etoposide", "irinotecan", "vinorelbine",
        "pemetrexed", "temozolomide", "capecitabine", "methotrexate",
        "zoledronic acid", "dexamethasone", "ondansetron", "prednisone",
    }

    def _base(name: str) -> str:
        words = name.split()
        while len(words) > 1 and words[-1] in {
            "hydrochloride", "calcium", "disodium", "sodium", "sulfate",
            "citrate", "acetate", "mesylate", "tartrate", "phosphate",
        }:
            words = words[:-1]
        return " ".join(words)

    # A drug with one labelled patient is trivially deterministic and says
    # nothing, so require several before treating it as evidence.
    _MIN_GENE_SUPPORT = 3
    smoking_gun = [
        (drug, next(iter(real)), sum(real.values()))
        for drug, _h, real in deterministic
        if _base(drug) in AGNOSTIC and sum(real.values()) >= _MIN_GENE_SUPPORT
    ]

    if smoking_gun:
        print("  BIOMARKER-AGNOSTIC DRUGS THAT PERFECTLY PREDICT A GENE:")
        for drug, gene, n in sorted(smoking_gun, key=lambda t: -t[2]):
            print(f"    {drug:<28} -> {gene:<10} in all {n} patients")
        print()
        print("  These are cytotoxic or supportive agents chosen without")
        print("  reference to any biomarker. In measured data their patients")
        print("  carry a spread of genes. A perfect mapping means the gene was")
        print("  not measured for that patient.")
        print()

    print("=" * 74)
    if smoking_gun or frac >= 0.9:
        print("  VERDICT: CIRCULAR")
        print()
        print("  The drug determines the gene for essentially every drug in the")
        print("  set. Real prescribing does not behave this way, so the biomarker")
        print("  was computed from the treatment rather than measured. Any")
        print("  concordance figure from these labels is an artifact of how they")
        print("  were built and cannot support a claim about accuracy.")
        print()
        print("  Fix: take the biomarker from the patient's sequencing record and")
        print("  the drug from the clinical record, join on patient ID only, and")
        print("  never let one derive the other.")
        return 1

    print("  VERDICT: not circular by this test")
    print()
    print("  Passing here means the labels are not drug-derived. It does not")
    print("  mean the benchmark is sound; selection and coverage still apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
