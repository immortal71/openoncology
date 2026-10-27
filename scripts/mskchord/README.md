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
the static table does not know (open and public, no auth), with CNA and
fusion lookups wired into the qualifying-alteration path:

```
Ranker: ran on 2,466 of 2,505 benchmarkable patients (98.4% coverage)
  top-1 exact drug matched:         1,740 (70.6%)
  top-1 same-class:                 2,454 (99.5%)
  top-3 exact drug in top three:    2,094 (84.9%)
  top-3 same-class in top three:    2,466 (100.0%)
  fair-bound top-3 exact
    (counting 39 no-prediction as misses):  83.6%
  true misses:                      0

Head-to-head vs an OncoKB-only baseline (ranker with CIViC fallback and
target-class filtering stripped out), scored on the same 2,505 benchmarkable
patients:
  coverage        OncoKB-only  85.9%   OpenOncology  98.4%   lift +12.6 pp
  top-3 exact     OncoKB-only  73.7%   OpenOncology  83.6%   lift  +9.9 pp
  top-3 class     OncoKB-only  85.9%   OpenOncology  98.4%   lift +12.6 pp
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
