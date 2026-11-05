# Benchmark reference

Each result belongs to a particular runner, dataset and date. The CHORD lookup experiment, frozen 50-case holdout and ongoing hard regression gate evaluate different things.

## MSK CHORD evidence-lookup benchmark

The October 27, 2026 saved run has 2,505 benchmarkable patients, 2,466 predictions and 2,094 exact top-three hits. Exact top-three agreement is 83.6% across all benchmarkable patients and 84.9% among predictions. Exact-or-class top-three agreement is 98.4% and 100%, respectively. Exact top-one agreement among predictions is 70.6%.

Sources: [metric summary](../validation_results/msk_chord_scored_metrics.json), [saved predictions](../validation_results/msk_chord_openoncology_run.json), [cohort](../validation_results/msk_chord_targeted_cohort.json) and [runner](../scripts/mskchord/run_openoncology_on_mskchord.py).

The runner selects qualifying alterations using each patient's received treatment and the benchmark target map. It calls the evidence lookup, sorts by level and uses a CIViC fallback. It does not call the application's full composite ranker. The target map also filters CIViC candidates, uses broad any-mutation rules for several genes and omits cancer context. The runner does not apply the application's indication gate. These choices limit claims of independent, whole-profile or label-specific clinical validation.

The saved OncoKB-only run has 2,151 predictions and 1,845 exact top-three hits (73.7% of all 2,505). The existing runner README describes removing CIViC and target-class filtering for the baseline, while the preprint says only CIViC changed. A reproducible baseline configuration and consistent methods description are needed before attributing the difference to CIViC alone. This documentation update does not change those saved runs or the protocol.

The experiment is retrospective, uses a US academic cohort and does not model treatment line. Same-class agreement is defined by the scorer's drug groups; it does not prove that the drugs are clinically interchangeable for a given patient. See [reproduction instructions](../scripts/mskchord/README.md) and the [research write-up](../preprints/msk_chord_benchmark.md), read with these scope limits.

## Latest observed hard-gate run

Main CI [run 41783696590](https://github.com/immortal71/openoncology/actions/runs/41783696590), November 4, 2026, at `cdff27f`, printed standard P@3 0.801, Hit@3 100% and zero false positives. All hard-gate checks passed. The 0.8222 figures retained below belong to an older artifact snapshot, not this CI run.

## ⚠️ Integrity rules

- Each section cites its saved artifacts or a dated CI run. Historical figures remain attributed to their original evaluation.
- Never edit numbers here to match desired output — run the gate and copy what it prints.  
- Never add benchmark cases by checking algorithm output first. Cases must be clinically sourced.  
- Never expand `known_drugs` in a benchmark case to manufacture a P@3 gain.  
- The pre-publication numbers are **frozen** — they reflect the exact system described in the preprint and cannot be retroactively improved.

---

## PRE-PUBLICATION baseline (published in preprint)

**Citation:** Kharel, A. (2026). *OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision Oncology.* Research Square. https://doi.org/10.21203/rs.3.rs-9707913/v1

**Run command used:**
```bash
python scripts/blind_external_validation.py --n-cases 50 --seed 11
```
Mode: OncoKB static fallback · no live CIViC · offline  
Artifact: `validation_results/holdout_50_metrics.json`

### Blinded 50-case oncologist holdout

| Metric | Value | Notes |
|--------|-------|-------|
| **Hit@3** | **0.900** | Gold-standard drug in top-3 for 90% of cases |
| **Standard Precision@3** | **0.508** | Ceiling for this mixed-difficulty holdout: **0.625** |
| **Normalised Precision@3** | **0.817** | Near-perfect when normalised for single-drug gold standards |
| **False Positives** | **0** | FP rate 0% — no spurious high-confidence recommendations |
| **Mean Reciprocal Rank (MRR)** | **0.883** | Gold drug appears near the top on average |
| **NDCG@3** | **0.883** | Strong ranking quality across the full holdout |

**Holdout composition:** 40 sensitivity cases (16 single-drug gold standard, 24 multi-drug gold standard) + 10 negative-control specificity cases.
**Source material:** JCO Precision Oncology, Annals of Oncology, Nature Medicine tumour board reports.
**Full case list:** `validation_results/holdout_50_results.txt` · **Per-case scoring:** `blind_review_key_scoring.json`

> **Why Standard P@3 = 0.508 while Hit@3 = 0.900?** Standard P@3 uses a fixed denominator of 3 regardless of how many gold-standard drugs exist. When a case has only one gold-standard drug, even a perfect top-3 result gives P@3 = 1/3 = 0.333. Most cases in precision oncology have a single targetable drug per mutation — this is expected behaviour, not a failure. The ceiling of 0.625 reflects the realistic maximum for this holdout's case mix.

> **2026-07-20 reconciliation note:** NDCG@3, the P@3 ceiling, and the single/multi-drug
> case split previously stated here (0.845, 0.650, 12/28) did not match either raw
> artifact (`holdout_50_results.txt`, `blind_review_key_scoring.json`) and have been
> corrected to the artifact values above. `holdout_50_metrics.json` (this section's cited
> source) does not itself contain NDCG/ceiling/split fields — those three values are
> sourced from the two artifacts named above instead.

---

## POST-PUBLICATION ongoing benchmark (hard gate, main branch)

**Run command:**
```bash
python scripts/hard_benchmark_gate.py
```
Mode: OncoKB static fallback · offline (no live API calls required)  
Artifact: `hard_benchmark_results.json` (updated on every gate run)

### Historical hard-gate artifact snapshot (May 2026)

| Metric | Value | Gate threshold | Status |
|--------|-------|----------------|--------|
| **Standard P@3** | **0.8222** (≈ 0.822) | ≥ 0.65 | ✅ PASS |
| **Hit@3** | **100.0%** | ≥ 90% | ✅ PASS |
| **False Positives** | **0** | ≤ 0 | ✅ PASS |
| Cases | 83 total | — | 75 sensitivity + 8 negative controls |

> **Why is post-pub P@3 higher than the paper?** The hard gate cases are curated specifically for the gate (known difficult variants, not a random holdout). The 50-case blinded holdout was drawn blindly from literature — a harder, more representative clinical mix. These are different benchmarks measuring different things. Do not compare the numbers directly.

### Change log (post-publication improvements)

| Date | Change | P@3 before | P@3 after |
|------|--------|-----------|-----------|
| 2026-05-03 | Repotrectinib NTRK evidence; EGFR exon20ins bug fix | ~0.800 | 0.817 |
| 2026-05-29 (early run) | FGFR2-BICC1/FGFR3-TACC3 aliases; CLDN18/DLL3/FOLR1 evidence + context overrides | 0.817 | 0.8178 |
| 2026-05-30 | Additional case/evidence updates since the 0.8178 run | 0.8178 | **0.8222** (historical artifact snapshot; see the dated CI result above) |

> The 0.817 / 0.8178 entries above are a same-week earlier snapshot, superseded by the
> 0.8222 historical snapshot in this section. See
> `docs/BENCHMARK_v0817_2026-05-29.md` for that snapshot's full detail (kept for
> forensic/methodology reference, not as a current number).

---

## TCGA real-patient coverage benchmarks

These are coverage benchmarks (does the system return *any* drug candidate?), not ranked-retrieval benchmarks.

### 100-case TCGA cohort

```bash
python scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json
```

Measured 2026-08-12. The request was for 100 cases and cBioPortal returned 72,
see the reproducibility note below.

| Tier | Patients | % |
|------|----------|---|
| Tier 1 (FDA-approved direct match) | 10 | 13.9% |
| Tier 2 (off-label FDA repurposing) | 31 | 43.1% |
| Tier 3 (clinical trial match) | 11 | 15.3% |
| No recommendation | 20 | 27.8% |
| **Total covered** | **52** | **72.2%** |

Artifact: [validation_results/real_patient_benchmark_100.json](../validation_results/real_patient_benchmark_100.json)

The per-patient VCF and biopsy files under `samples/real/` are regenerated on every
run from whatever cohort cBioPortal returns, so they are not pinned to the numbers
above.

#### Why this is no longer 100%

The earlier table reported 36% Tier 1, 64% Tier 2 and 100% total coverage. That
figure counted the Tier 4 custom-design escalation path as covered. Custom drug
design now requires explicit user action and is never auto-generated, so
`tier4_custom_drug()` is no longer invoked from the benchmark loop and
`CUSTOM_DESIGN` is unreachable. Those cases report as "no recommendation"
instead of being counted as covered.

So the drop is a change in what counts as coverage, not a regression in the
pipeline. The old number answered "did we produce any output, including an
offer to design something", and the new one answers "did we find a drug".
The 20 uncovered cases are still eligible for manual custom-design escalation,
reported as `manual_tier4_eligible_cases` in the artifact.

#### The oncology gate removed nothing here

The WHO ATC gate (`api/services/oncology_atc.py`) excluded 0 drugs across all 72
cases. That is not evidence the gate is inert. This benchmark's Tier 2 additionally
requires a cancer-context match or trial backing before a drug is admitted, which
is stricter than production's Tier 2, so the cardiac glycosides and beta blockers
the gate was built to remove never entered this code path in the first place.
The gate is measured here because the benchmark should run what production runs,
not because this cohort exercises it.

#### Reproducibility

By default the cohort is drawn live from cBioPortal, so the patient set differs
between runs: `--n 100` returned 72 cases and `--n 200` returned 142 on the
2026-08-12 run. A percentage from a live draw is a reading taken on a date, not
a score, and comparing two of them compares two cohorts as well as two
pipelines. A real regression is indistinguishable from a different draw.

Pass `--manifest` to replay a pinned cohort instead. The two above are committed,
so the numbers in this document can be checked rather than taken on trust:

```bash
python scripts/fetch_real_patients.py \
    --manifest validation_results/benchmark_cohort_72.json \
    --out-json real_patient_benchmark_100.json

python scripts/fetch_real_patients.py \
    --manifest validation_results/benchmark_cohort_142.json \
    --out-json real_patient_benchmark_200.json
```

A manifest carries everything a case needs, so replaying one makes no cBioPortal
call for patient selection at all. Use `--write-manifest PATH` to pin a fresh
draw for future comparison.

Use a pinned cohort for anything you intend to compare over time, and a live
draw only when you deliberately want a fresh sample.

### 200-case TCGA cohort

```bash
python scripts/fetch_real_patients.py --n 200 --out-json real_patient_benchmark_200.json
```

Measured 2026-08-12. `--n 200` returned 142 cases.

| Tier | Patients | % |
|------|----------|---|
| Tier 1 (FDA-approved direct match) | 30 | 21.1% |
| Tier 2 (off-label FDA repurposing) | 58 | 40.8% |
| Tier 3 (clinical trial match) | 16 | 11.3% |
| No recommendation | 38 | 26.8% |
| **Total covered** | **104** | **73.2%** |

The 200-patient set is intentionally harder and includes many variants with no
direct approved match, which makes it useful for evaluating escalation behaviour
and safe abstention.

Same correction as the 100-case set above. The earlier table read 7.5% Tier 1,
92.5% "custom-design escalation path" and 100% covered. The 92.5% was the
escalation path being counted as coverage. It is now reported as 38 cases with no
recommendation, still eligible for manual custom-design escalation.

The oncology gate excluded 0 drugs here too, for the same reason given above.

Artifact: [validation_results/real_patient_benchmark_200.json](../validation_results/real_patient_benchmark_200.json)

For comparison, the previous committed artifact recorded `DIRECT_FDA` 15,
`FDA_REPURPOSING` 0, `INVESTIGATIONAL_REPURPOSING` 0, `CUSTOM_DESIGN` 185 and
`NONE` 0. Both repurposing tiers were empty, so the whole of that 100% above the
7.5% Tier 1 figure was the custom-design path being counted as coverage.

---

## 5-fold cross-validation (not previously cited anywhere)

The historical record reports an additional 5-fold CV run in `benchmark_results.json`.
That file is not committed in this revision, so the following figures are retained as historical claims rather than independently verified current results
(n=60 sensitivity cases, 623 total cases including negatives): mean CV score 0.8639
(std 0.0773), normalised P@3 = 0.9424, standard P@3 = 0.5758, Hit@3 = 0.9818, MRR =
0.9273, FP rate = 0.0. This run was not previously referenced in any doc — flagged here
for visibility rather than left silently orphaned. It should not be treated as
independently confirmed until its methodology (fold construction, case source) is
re-verified; it is listed here as a pointer, not yet as a headline claim.

---

## How to run a verified benchmark

```bash
# 1. Activate environment
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate    # Linux/macOS

# 2. Run the hard gate (results go to hard_benchmark_results.json)
python scripts/hard_benchmark_gate.py

# 3. Run the blinded 50-case holdout (replicates the paper run)
python scripts/blind_external_validation.py --n-cases 50 --seed 11

# 4. Real-patient coverage benchmark
python scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json
python scripts/fetch_real_patients.py --n 200 --out-json real_patient_benchmark_200.json
```

---

## Metric definitions

| Metric | Formula | Notes |
|--------|---------|-------|
| **Standard P@3** | (hits in top-3) / 3 | Fixed denominator = 3. Penalises single-drug gold standards. Use for comparison across systems. |
| **Normalised P@3** | (hits in top-3) / min(3, \|gold\|) | Denominator = number of gold drugs (≤3). Rewards systems that correctly identify all relevant drugs. |
| **Hit@3** | 1 if ≥1 gold drug in top-3, else 0 | Binary retrieval success. Clinical relevance metric. |
| **MRR** | 1 / rank_of_first_hit | Mean over all cases. Rewards ranking the correct drug higher. |
| **NDCG@3** | Discounted cumulative gain at k=3 | Graded relevance; penalises correct drugs appearing lower in the list. |
| **False Positive** | High-confidence recommendation with no evidence support | Defined per-case in benchmark spec. Gate requires FP = 0. |
