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

- MSK-CHORD's structural-variant endpoint is not exposed in this fetcher,
  so fusion-only expectations (ALK, ROS1, RET, NTRK) are reported as
  **UNEVALUABLE** rather than counted as misses. 473 patients fall here.
  This is a feature cBioPortal doesn't expose at the same POST endpoint
  as mutations; a follow-up is to pull structural variants per-sample.
- Patients who received palbociclib, abemaciclib, ribociclib, everolimus
  or similar receptor-driven drugs are typically marked **miss**, because
  those drugs are chosen by receptor status (HR+/HER2-) and not by a
  genomic alteration. This is correct: a mutation ranker should not be
  measured against them.

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

## As of 2026-10-26

Ground-truth cohort:

```
5,190 patients with targeted-therapy events + alteration data
  benchmarkable: 2,222 (an alteration matches the drug under its label)
  unevaluable (fusion-only, SV endpoint not pulled): 473
  no qualifying alteration for any received drug: 2,495
```

OpenOncology ranker against the benchmarkable subset, using the committed
static evidence table (no OncoKB token, no external APIs):

```
Ranker: ran on 1,697 of 2,222 benchmarkable patients
  exact drug in top 3:        1,077 (63.5%)
  same-class drug in top 3:   1,697 (100.0%)
```

The remaining 525 benchmarkable patients had no static-table entry for their
exact (gene, variant) pair; most are HER2 amplifications and EGFR variants
outside the hotspot set. Running with a live OncoKB token on this cohort is
the next step.

Per-drug coverage of the benchmarkable set:

| Drug | Benchmarkable | Received |
|---|---:|---:|
| osimertinib | 1035 | 1058 |
| erlotinib | 461 | 493 |
| alpelisib | 209 | 230 |
| afatinib | 146 | 193 |
| olaparib | 128 | 442 |
| tucatinib | 94 | 126 |
| sotorasib | 92 | 98 |
| encorafenib | 83 | 86 |
| trametinib | 83 | 126 |
| dabrafenib | 74 | 87 |
