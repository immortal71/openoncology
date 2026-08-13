# Oncologist Concordance Benchmark (Plain-Language)

## The previous 100% figure is retracted

This page used to report **100% equivalence-adjusted concordance (36/36)**. That
number was an artifact of how the answer key was built, and it is withdrawn.

`scripts/build_concordance_labels.py` used to contain a `DRUG_BIOMARKER_MAP`
that read each patient's gene off the drug they had been given. A patient who
received trastuzumab was labelled "ERBB2 Amplified". A patient who received
vemurafenib was labelled "BRAF V600E". No sequencing record was consulted for
any of it.

The benchmark then asked the pipeline "which drug would you give for ERBB2
amplification?", and scored the answer against trastuzumab, which is where the
ERBB2 label had come from in the first place. It is the same question in both
directions, so a high score was guaranteed before any code ran. Only 128 of the
1,713 labels carried a gene at all, and the 100% was measured on 36 of them.

The clearest evidence was in the labels themselves. Zoledronic acid is a
bisphosphonate given to protect bone; it mapped to ERBB2 in all four of its
patients. Cisplatin mapped to EGFR in all eight. Fluorouracil mapped to ERBB2 in
all five. These drugs are chosen without reference to any biomarker, so in
measured data their patients carry a spread of genes. A perfect mapping means
the gene was copied from a co-administered targeted agent rather than measured.

`scripts/detect_label_circularity.py` measures this property and exits non-zero
when it finds it. It failed on the old labels and passes on the current ones.

## How the answer key is built now

Two sources that cannot see each other, joined on patient id and nothing else:

| Field | Comes from | Fetched by |
|---|---|---|
| Biomarker | The patient's own cBioPortal sequencing record: somatic mutations and GISTIC amplification / deep-deletion calls | `scripts/fetch_concordance_biomarkers.py` |
| Drug | The therapeutic agents on the patient's GDC clinical record | `scripts/clinical*.tsv` exports |

No drug influences which biomarker a patient gets, and no biomarker influences
which drug. The gene universe is the published MSK-IMPACT 468-gene panel, read
live from cBioPortal (Cheng DT et al., J Mol Diagn 2015;17:251). That panel was
chosen because it is what a real sequenced patient's report contains and it was
defined with no reference to this repository. Selecting genes from this repo's
own evidence table would have restricted the answer key to questions the
pipeline already answers, which inflates the score the same way the drug map did.

## The denominator

A patient counts only if both sources have them.

| | Patients |
|---|---|
| With a recorded therapeutic agent (GDC) | 1,713 |
| With at least one panel alteration (cBioPortal) | 3,011 |
| Dropped: drug recorded but never sequenced | 0 |
| Dropped: sequenced but nothing on the panel | 129 |
| **Scored (both sources present)** | **1,584** |

By cohort: BRCA 738, GBM 410, LUAD 166, SKCM 148, COAD 122.

## Results

Two configurations, both against the same 1,584 patients. Tier 1 is the
FDA-approved evidence table; Tier 2 repurposing is excluded here, so these are
the strict numbers.

| Configuration | Cases with a prediction | Exact Top-1 | Exact Top-3 | Class Top-1 | Class Top-3 |
|---|---|---|---|---|---|
| Primary alteration only | 745 / 1,584 | 0.0% (0/745) | 0.81% (6/745) | 0.27% (2/745) | 1.34% (10/745) |
| Full sequencing report | 1,232 / 1,584 | 0.0% (0/1232) | 1.38% (17/1232) | 0.32% (4/1232) | 1.95% (24/1232) |

"Primary alteration only" submits one alteration per patient. "Full sequencing
report" submits every alteration the patient carries and re-ranks the pooled
candidates, which is closer to what a tumour board sees and removes any
dependence on which alteration the label happens to name first. Reproduce with:

```
python scripts/benchmark_oncologist_concordance.py \
  --labels-json scripts/concordance_labels.json --tier1-only
python scripts/benchmark_oncologist_concordance.py \
  --labels-json scripts/concordance_labels.json --all-biomarkers --tier1-only
```

## What the low number means

It is close to zero, and the reason is visible in the data rather than
mysterious. The drugs these patients actually received are overwhelmingly
cytotoxic chemotherapy and endocrine therapy:

| Drug | Patients |
|---|---|
| Cyclophosphamide | 493 |
| Temozolomide | 339 |
| Paclitaxel | 267 |
| Tamoxifen | 254 |
| Anastrozole | 236 |
| Docetaxel | 207 |
| Fluorouracil | 196 |

The pipeline recommends targeted agents: abemaciclib, cetuximab, alpelisib,
binimetinib. Those two lists barely intersect, so concordance is near zero.

That is a finding about the dataset, not only about the pipeline.
`scripts/diagnose_concordance_dataset.py` reaches the same conclusion from the
other direction: in these TCGA cohorts treatment was chosen by diagnosis and
protocol, not by the patient's sequenced gene. Scoring a gene-to-drug engine
against protocol-era chemotherapy asks it to emit the same cytotoxic for many
unrelated genes, which it can only do by ignoring the gene.

So the honest reading is:

- **This benchmark does not show the pipeline is accurate.** It shows the
  pipeline disagrees with what TCGA-era oncologists prescribed.
- **It also does not show the pipeline is inaccurate.** The answer key was not
  produced by biomarker-driven prescribing, so it cannot settle that question
  either way.
- A benchmark whose answer key *was* biomarker-driven is
  [BENCHMARK_NCI_MATCH.md](BENCHMARK_NCI_MATCH.md), where each trial arm is an
  explicit published "biomarker X receives drug Y" committee decision. Read that
  one for a claim about drug-assignment agreement, with the limitations stated
  there.

A small honest number measured against a real answer key is worth more than
100% measured against a tautology, but neither number is evidence of clinical
accuracy on its own.

## What "Top-1" and "Top-3" mean

- Top-1: did our highest-ranked drug match a drug the oncologist chose?
- Top-3: did any of our top three match?

Class matching counts clinically interchangeable agents in the same class as a
hit (for example vemurafenib and dabrafenib, both BRAF inhibitors), because some
records date from 2011 to 2014 when different agents in the same class were
standard. Class-adjusted results are always reported separately from exact
match, never merged into it.

## Important safety note

This benchmark shows retrospective agreement with real-world oncologist
decisions. It does not replace an oncologist, a tumour board, or clinical
judgment. The tool is for decision support and evidence review, not autonomous
treatment decisions.

## Data and script sources

- Biomarker fetch: `scripts/fetch_concordance_biomarkers.py` (cBioPortal)
- Label builder: `scripts/build_concordance_labels.py`
- Circularity gate: `scripts/detect_label_circularity.py`
- Scorer: `scripts/benchmark_oncologist_concordance.py`
- Labels: `scripts/concordance_labels.json`
- Per-case results: `artifacts/oncologist_concordance_results.json` (full sequencing
  report, Tier 1 only, the second row of the results table)
- Dataset diagnosis: `scripts/diagnose_concordance_dataset.py`
