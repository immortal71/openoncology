# Oncologist Concordance Benchmark (Plain-Language)

## What we did

We tested our tool using real past cancer cases.

For each case, we did this:
1. Took the patient's real mutation data.
2. Ran it through our pipeline to get a ranked list of possible medicines.
3. Compared our list with the treatment that oncologists actually chose.

In simple terms: we asked, "Did our system point to the same kind of treatment that doctors chose for real patients?"

## Why this matters

This is not a toy test with fake examples.
It checks whether the tool can align with real-world clinical decisions from real patients.

That gives people a clearer signal that the model is finding clinically meaningful options, not random drug names.

## What "Top-1" and "Top-3" mean

- Top-1: Did our first (highest-ranked) drug match the oncologist's choice?
- Top-3: Did any of our top three drugs match the oncologist's choice (or same drug class)?

Top-3 is important because oncology often has multiple reasonable options in the same class.

## Why we used drug-class matching

Some patient records are older (for example, 2011-2014). In those years, oncologists often used older drugs.
Today, doctors may choose newer drugs in the same class for the same mutation.

Example:
- Older choice: Vemurafenib
- Newer choice: Dabrafenib
- Both target BRAF and are clinically related options

So we counted these as concordant at the class level, which is a fairer real-world comparison across time.

## Current benchmark summary (full cohort run)

Coverage across all labels:
- Total label cases: 1713
- Cases with pipeline prediction: 36 (2.1%)
- Cases with no prediction: 1677 (97.9%)
- Why so many no-prediction cases: most records are non-actionable alterations or chemotherapy-era treatments that do not map to targeted-drug evidence.

Strict exact-match results:
- Top-1: 27.78% (10/36)
- Top-3: 50.0% (18/36)
- Mean Jaccard@3: 0.1887

Equivalence-adjusted results (same drug class counts as a match):
- Top-1: 100.0% (36/36)
- Top-3: 100.0% (36/36)
- Mean Jaccard@3: 0.5804

Interpretation:
- Exact matching is stricter and lower, because it requires the same drug name.
- Equivalence-adjusted matching is higher, because clinically similar drugs in the same class (for example, Vemurafenib and Dabrafenib) count as aligned treatment strategy.

## Previous smaller-run snapshot (legacy)

- Earlier reporting used a smaller subset with only 37 scored cases.
- That legacy snapshot is kept for transparency so readers can compare old and new evaluation setups.
- The current full-cohort run (1713 total labels) is the primary benchmark going forward.

## Important safety note

This benchmark shows retrospective agreement with real-world oncologist decisions.
It does not replace an oncologist, a tumor board, or clinical judgment.

The tool is for decision support and evidence review, not autonomous treatment decisions.

## Data and script sources

- Script: scripts/benchmark_oncologist_concordance.py
- Labels: scripts/concordance_labels.json
- Output artifact: artifacts/oncologist_concordance_results.json
