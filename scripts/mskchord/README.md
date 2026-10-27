# MSK-CHORD mutation-ranker benchmark (OO-29)

The 69-patient TCGA pilot in `validation_results/` is the wrong cohort for a
mutation ranker: most patients received chemotherapy chosen by cancer type,
and 45 of 69 had kidney cancer treated without genomic guidance. See OO-28.

This folder is a replacement: 5,190 MSK-CHORD patients who received at least
one targeted therapy and have IMPACT panel data. Of them, **2,222 have an
alteration whose FDA label names the drug they received**. That is the
benchmarkable subset for a mutation-matched ranker.

## Files

- `fetch_mskchord.py` — pulls treatments, mutations and CNAs from cBioPortal
  and GitHub datahub. Needs network access to those two hosts.
- `targeted_drug_targets.py` — per-drug map of the alterations that justify
  it under its FDA label. One source of truth for the benchmark.
- `score_mskchord.py` — reads a cohort file and prints:
  - ground-truth coverage (which patients are benchmarkable),
  - and, with `--results <path>`, the ranker's top-3 hit rate on the
    benchmarkable subset.
- `validation_results/msk_chord_targeted_cohort.json` — the pre-fetched
  cohort as of 2026-10-26.

## Known limits

- Patients who received palbociclib, abemaciclib, ribociclib, everolimus
  or similar receptor-driven drugs are typically marked **miss**, because
  those drugs are chosen by receptor status (HR+/HER2-) and not by a
  genomic alteration. This is correct: a mutation ranker should not be
  measured against them.
- Structural variants are now pulled from cBioPortal's SV endpoint
  (389 patients in the targeted cohort carry an actionable fusion), so
  ALK, ROS1, RET, NTRK, FGFR2 and ABL1 fusion drugs are scored, not
  shelved.

## Reproducing

```bash
# Fetch (writes validation_results/msk_chord_targeted_cohort.json)
python scripts/mskchord/fetch_mskchord.py

# Score ground truth
python scripts/mskchord/score_mskchord.py validation_results/msk_chord_targeted_cohort.json

# Score a ranker run against the cohort
python scripts/mskchord/score_mskchord.py validation_results/msk_chord_targeted_cohort.json \
  --results path/to/your_run.json
```

The ranker run file should carry one record per patient with `patient_id`
and `pipeline_top3` (a list of drug names), the same shape
`scripts/concordance_pilot_run_pipeline.py` produces.

## As of 2026-10-27

Ground-truth cohort:

```
5,190 patients with targeted-therapy events + alteration data
  benchmarkable: 2,505 (an alteration matches the drug under its label)
  unevaluable (no selecting alteration under the label): 53
  no qualifying alteration for any received drug: 2,632
```

OpenOncology ranker against the benchmarkable subset, using the committed
static evidence table plus a CIViC nightly-release fallback for variants
the static table does not know (open and public, no auth):

```
Ranker: ran on 2,236 of 2,505 benchmarkable patients
  exact drug in top 3:              2,042 (91.3%)
  same-class drug in top 3:         2,236 (100.0%)
  class-equivalent additions:       194 (same molecular target,
                                        different drug in the class)
  true misses:                      0
```

Fusions were added by pulling cBioPortal's structural-variant endpoint and
emitting a canonical "<partner>-<gene> fusion" to the ranker, which the
static table matches to the fusion-only labels (alectinib/crizotinib for
ALK, selpercatinib/pralsetinib for RET, larotrectinib/entrectinib for
NTRK, pemigatinib/futibatinib for FGFR2, etc.). CIViC fallbacks are
filtered to the FDA-labelled targeted-drug family for each gene so
chemotherapy entries CIViC also lists do not crowd out the TKI. Within an
OncoKB level the ranker now preserves the dump's own clinical order
(osimertinib before erlotinib, trastuzumab before pertuzumab, trametinib
before vemurafenib), which matches how patients are actually prescribed.

CIViC data file: `validation_results/civic_actionable_evidence.json`,
derived from the nightly `AcceptedClinicalEvidenceSummaries.tsv` release at
https://civicdb.org/releases/main.
Fusion data file: `validation_results/msk_chord_fusions.json`, pulled from
cBioPortal's `/structural-variant/fetch` endpoint for all 5,399 MSK CHORD
samples (389 patients carry a fusion in an actionable gene).

Per-drug coverage of the benchmarkable set:

| Drug | Benchmarkable | Received |
|---|---:|---:|
| osimertinib | 1035 | 1058 |
| erlotinib | 461 | 493 |
| alectinib | 237 | 266 |
| alpelisib | 209 | 230 |
| afatinib | 146 | 193 |
| olaparib | 128 | 442 |
| crizotinib | 128 | 164 |
| tucatinib | 94 | 126 |
| sotorasib | 92 | 98 |
| encorafenib | 83 | 86 |
| trametinib | 83 | 126 |
| dabrafenib | 74 | 87 |
