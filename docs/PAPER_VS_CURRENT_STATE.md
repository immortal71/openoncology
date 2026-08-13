# Paper vs. Current Repository State — Reconciliation Record

**Preprint**: "OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and
De Novo Custom Drug Discovery in Precision Oncology"
**DOI**: 10.21203/rs.3.rs-9707913/v1
**Posted**: May 18, 2026 (confirmed directly from the Research Square page's `postedDate`
field: `"postedDate":"May 18th, 2026"`)
**This document verified against**: live fetch of the preprint full text
(`https://www.researchsquare.com/article/rs-9707913/v1`) and the current state of this
repository (git history + running code), on the date this document was written.

This is a factual reconciliation record. It does not recommend a course of action.

---

## Section 1 — As published in the preprint (verbatim facts)

All figures below were fetched directly from the preprint's own HTML/text and quoted
verbatim; none are taken from memory or from repo documentation.

### 1.1 Ranking algorithm weights (Methods, Section 2.2 "Stage One: Variant Calling and
Drug Matching")

> "Drug candidates are ranked by a weighted composite score integrating five evidence
> signals: **DiffDock binding confidence 30%** ... **OpenTargets association score 25%**
> ... **OncoKB actionability level 25%** ... **AlphaMissense pathogenicity 10%** ...
> **Clinical trial phase 10%**"

Five signals, weights sum to 100%. No CIViC signal is mentioned in this table anywhere in
the preprint.

### 1.2 50-case blinded holdout (Results, Section 3.1 "Blinded Oncologist Holdout (n = 50)")

| Metric | Result |
|---|---|
| Hit@3 | 0.900 |
| Standard Precision@3 | 0.508 (ceiling: 0.625) |
| Normalised Precision@3 | 0.817 |
| Mean Reciprocal Rank | 0.883 |
| False positive rate | 0.000 |

Quoted directly: *"a blinded 50-case oncologist holdout yielded Hit@3 = 0.900, Standard
Precision@3 = 0.508 (ceiling: 0.625), Normalised Precision@3 = 0.817, Mean Reciprocal
Rank = 0.883, and zero false-positive recommendations."* The holdout is stated to include
12 Level 3–4 literature-sourced cases and 6 negative controls.

### 1.3 TCGA benchmarks (Results, Section 3.2, table titled "Tier 1 (FDA-approved) / Tier 2
(Repurposing) / Stage 2 escalation / Empty outputs")

| Cohort | Tier 1 | Tier 2 | Stage 2 escalation | Coverage |
|---|---|---|---|---|
| 100-patient | 36 (36%) | 64 (64%) | 0 (all stage 1 matched) | 100% (0 empty) |
| 200-patient | 15 (7.5%) | 0 | 185 (92.5%) | 100% (0 empty) |

> Recorded verbatim as published. This table no longer reproduces: coverage
> re-measured 2026-08-12 is 72.2% and 73.2% for the two cohorts, because the 100%
> counted the stage 2 escalation path as covered and custom design is now
> manual-only. See Section 3.

### 1.4 Oncologist concordance (Section 2.5 / Section 3.3 "Oncologist Concordance")

Concordance analysis is stated as run against **n = 1,713 label cases** from multi-cohort
TCGA clinical records. Quoted results table (Section 3.3):

| Match type | Top-1 | Top-3 | Jaccard |
|---|---|---|---|
| Exact match (strict) | 27.78% (10/36) | 50.0% (18/36) | 0.1887 |
| Equivalence-adjusted | 100% (36/36) | 100% (36/36) | 0.5804 |

The 36 in each denominator refers to the **36 actionable TCGA cases** within the 1,713
labels (quoted: *"Equivalence-adjusted oncologist concordance reached 100% at both Top-1
and Top-3 across 36 actionable TCGA cases"*). The paper explains the 97.9% "no-prediction"
rate on the full 1,713 as expected, reflecting TCGA's unselected population (most patients
are non-actionable or received cytotoxic chemotherapy).

> Recorded verbatim as published. **This table is retracted, not merely stale.** The
> answer key derived each patient's gene from the drug they received, so the benchmark
> could not have returned anything but a high number. Rebuilt against sequencing
> records on 2026-08-13: class-adjusted Top-3 is 1.95%, not 100%. See Section 3.

### 1.5 AlphaFold structure generation completion (Section 3.4 "Stage Two: Discovery Brief")

Quoted verbatim: *"AlphaFold structure generation was triggered for all 185 cases and
completed successfully for 178 (96.2%); the seven failures were attributable to AlphaFold
Server rate limiting and were logged as pending rather than errors."*

This is a specific, falsifiable claim: it asserts real network calls to AlphaFold Server,
with **rate limiting** (an external-API-only failure mode) as the stated cause of the seven
failures.

---

## Section 2 — Verified against current code and git history

### 2.1 Do the live ranking weights match the paper's Table 2.2?

**No. The published Methods no longer describe the deployed algorithm.**

Current weights, quoted directly from `api/ai/ranking_config.py:52-57`:

```python
binding: float = 0.15          # DiffDock structural binding confidence [0,1]
opentargets: float = 0.15      # OpenTargets target-disease association [0,1]
oncokb: float = 0.40           # OncoKB actionability level (mapped to score)
alphamissense: float = 0.10    # AlphaMissense pathogenicity [0,1]
clinical_phase: float = 0.10   # Highest clinical trial phase / approval status
civic: float = 0.10            # CIViC evidence tier (A–E mapped to score)
```

This is a **six-signal** model (the paper's table has five; CIViC at 10% is absent from
the paper entirely), and the two largest paper weights are inverted in the live code:
OncoKB is 40% (paper: 25%) and DiffDock is 15% (paper: 30%).

**Git history of this divergence, checked directly (not assumed):**

- **2026-03-19** (`c66af7b`, "Initial commit: OpenOncology AI drug repurposing platform")
  — the repo's genesis state had weights **matching the paper exactly**: DiffDock 0.30,
  OpenTargets 0.25, OncoKB 0.25, AlphaMissense 0.10, Phase 0.10 (verified via
  `git show c66af7b:api/ai/ranking.py`).
- **2026-05-03** (`589e47e`, "Add benchmark validation, concordance tooling, and README
  updates") — `api/ai/ranking_config.py` was introduced in this commit and changed the
  weights to the current 0.40/0.15/0.15/0.10/0.10/0.10 (CIViC added). This is the **only**
  commit that has ever touched this file (`git log --follow` on the file returns exactly
  one commit).
- **No commit since 2026-05-03 has modified these weights.** They are unchanged through
  the current HEAD.

**Timeline consequence**: the weight change (2026-05-03) predates the preprint's posting
date (2026-05-18) by 15 days. The paper's Methods 2.2 table describes the algorithm's
*original* (March 19) configuration — the configuration that was **no longer running**
by the time the paper was posted. This is not a case of the code drifting after
publication; the deployed code had already diverged from the paper before the paper went
public.

### 2.2 Was real AlphaFold Server / DiffDock access ever configured, explaining the
178/185 (96.2%) completion claim — or was that number always against fallback/stub
structures?

**Checked directly via git history and current code/config state — real access was never
configured in this repository, at any commit, on any branch.**

- `ai/services/alphafold.py` (introduced 2026-04-26, commit `64382aa`) is a real, working
  HTTP client (not a stub) — it POSTs to `https://alphafoldserver.com/api/fold`, polls for
  job completion, and reads an optional bearer token via
  `token = os.getenv("ALPHAFOLD_API_KEY", "").strip()` (line 46). If no token is present,
  requests are simply sent unauthenticated; if the server returns 401/403, the function
  logs a warning and returns `None`, and callers fall back to wild-type EBI structures
  (per the module's own docstring).
- `git log --all -p -S "ALPHAFOLD_API_KEY"` across the entire history and all branches
  returns only the code that *reads* the variable — never a commit that *sets* it to a
  real value anywhere (`.env`, `.env.example`, CI config, or otherwise).
- Current `.env` and `.env.example` were checked directly: **`ALPHAFOLD_API_KEY` does not
  appear in either file.**
- `ai/diffdock/score.py` expects a cloned `DiffDock/` model directory at
  `DIFFDOCK_DIR` (default `ai/diffdock/DiffDock/`). Checked directly:
  **`ai/diffdock/` contains only the wrapper code (`score.py`, `prepare_inputs.py`,
  `__init__.py`) — no cloned `DiffDock/` model directory exists at that path or anywhere
  else in the repository, at the current commit.**
- This repo's own `PROJECT_COMPLETION_STATUS.md` (lines 190–209, added 2026-07-20 in
  commit `cb424eb`, one day before this document) independently reached the same
  conclusion after its own investigation: *"Confirmed 2026-07-20: neither is currently
  configured in this environment... Practical consequence: every benchmark run to date
  (50-case holdout, hard clinical gate, industry-grade audit) almost certainly scored
  binding against wild-type EBI structures or produced no `binding_score` at all — not
  mutation-specific DiffDock poses."*

**Conclusion**: no state of this repository's git history — checked from the initial
commit through the current HEAD — has ever had a real AlphaFold Server credential or a
cloned DiffDock model directory present. The paper's 178/185 (96.2%) AlphaFold completion
figure, with "AlphaFold Server rate limiting" cited as the cause of the 7 failures, cannot
be reproduced or explained from anything committed to this repository. Either that
benchmark run happened in an environment with credentials/a DiffDock install that were
never committed here, or the figure does not reflect what this codebase, as committed, has
ever been able to do. This document does not speculate further on which.

### 2.3 Hit@3 0.900 → 0.975 correction — ERRATUM.md search

**No such file, and no such correction, exists anywhere in this repository's history.**

- `find` across the entire working tree (tracked and untracked) for any file named
  `*erratum*` (case-insensitive): **zero results.**
- `git log --all --diff-filter=A --name-only` (every file ever added, on every branch,
  across all history) filtered for "erratum": **zero results** — no `ERRATUM.md` was ever
  created and later deleted; it simply never existed.
- `git log --all -p -S "0.975"` (every commit, every branch, searching for the literal
  string "0.975" being added or removed anywhere): **zero results.**
- A broader live-tree grep for `0.975` or `97.5%` across all `.md`/`.py`/`.json` files:
  **zero results.**

**Conclusion**: the premise of a Hit@3 0.900→0.975 correction, whether in a submitted
preprint version or only in repo docs, is not supported by anything in this repository.
No such figure or correction exists in the current working tree, in any historical commit,
or on any branch.

---

## Section 3 — What's new since publication (May 18, 2026), not in the paper at all

The following did not exist when the preprint was posted and are not described anywhere
in the preprint text:

- **Industry-grade validation audit** (`scripts/industry_grade_validation.py`,
  `industry_validation_report.json`). Live case counts, checked directly from the running
  code (`api/services/benchmark.py`):
  - `ADDITIONAL_VALIDATION_CASES`: 375 (current, post-reconciliation)
  - `HARD_CLINICAL_CASES`: 88
  - `TRIAL_DERIVED_CASES`: 15
  - An intermediate historical size of this dataset (n=222, expanded from an original
    n=90) is referenced in `PROJECT_COMPLETION_STATUS.md` — that number describes a
    prior state of the dataset, not its current size.
- **Gate-gaming removal** (this session and the immediately preceding one, dated
  2026-07-20/21): 105 cases (37 from "Batch 37" plus 68 multi-drug cases from "Batch 54")
  were removed from `ADDITIONAL_VALIDATION_CASES` for having been selected specifically
  to pass a `multi_drug_fraction` threshold rather than reflecting natural case
  prevalence. `multi_drug_fraction` was also removed from the pass/fail readiness gates
  in `scripts/industry_grade_validation.py` and is now reported as a descriptive
  statistic only. Re-running the script against the resulting reconciled 375-case
  dataset gives `multi_drug_fraction = 0.552` (down from a pre-fix 0.6695).
- **Full Docker Compose end-to-end pipeline verification** (this session): the first
  confirmed real run of upload → genomic pipeline → AI analysis → completed result
  through the actual `docker-compose.yml` stack, using `samples/egfr_t790m_demo.vcf`.
  Result: both mutations (EGFR T790M, TP53 R175H) correctly extracted with ClinVar/COSMIC
  IDs intact, and a generated patient-facing summary. Prior to this session,
  `PROJECT_COMPLETION_STATUS.md` stated directly: *"A full live Docker Compose end-to-end
  run (real submission → real result) has not yet [happened]."*
- **10 infrastructure bugs found and fixed** in the course of the above verification
  (commit `f47a036`, this session): two frontend build failures (wrong import style;
  a TypeScript type-narrowing error); a self-referential import bug in
  `api/ai/ranking.py`; a Django-only Celery scheduler flag that isn't installed and isn't
  needed; broken healthchecks (missing `curl` in two base images, a disabled Keycloak
  health endpoint, and `$HOSTNAME` not being expanded in exec-form healthcheck arrays);
  MinIO rejecting encrypted uploads with no KMS configured; a missing `psycopg2-binary`
  dependency for the synchronous Celery DB session; a `PYTHONPATH` misconfiguration
  breaking worker imports; a structural bug where the repository's actual `ai/` package
  (`alphamissense/`, `diffdock/`, `repurposing/`, `services/`) was never included in the
  Docker build context at all (only an unrelated stub `api/ai/` shipped); and a
  `DetachedInstanceError`/`UnboundLocalError` pair in the AI worker's result-assembly
  code path.
- **ENVIRONMENT/SENTRY_DSN production-safety hardening** (commit `f59e55c`, this
  session): `config.py`'s existing production-settings validator (which already hard-
  fails if `MINIO_SECRET_KEY` is left at its insecure default in production) was extended
  to also hard-fail if `ENVIRONMENT=development` while `SENTRY_DSN` is set — closing a
  gap in the safety net around a dev-mode pipeline shortcut introduced during the Docker
  verification work above.

- **The 100% oncologist-concordance figure in Section 1.4 is retracted.** This is a
  stronger statement than "no longer reproduces": the number was never measurable.
  `scripts/build_concordance_labels.py` carried a `DRUG_BIOMARKER_MAP` that assigned
  each patient a gene based on the drug they had been given, with no reference to any
  sequencing record. Trastuzumab meant ERBB2, vemurafenib meant BRAF V600E. The
  benchmark then asked which drug fits that gene and scored the answer against the drug
  the gene had been copied from. The tell was in the labels: zoledronic acid, a
  bisphosphonate for bone health, mapped to ERBB2 in all 4 of its patients, and
  cisplatin to EGFR in all 8. Biomarker-agnostic agents cannot perfectly predict a gene
  in measured data. The map is deleted; biomarkers now come from the patient's
  cBioPortal mutation and copy-number record, drugs from their GDC clinical record, and
  the two are joined on patient id only. Of 1,713 patients with a recorded drug, 1,584
  also have a panel alteration and are scored. Class-adjusted Top-3 on the full
  sequencing report is 1.95% (24 of 1,232 with a prediction), and exact Top-1 is 0.0%.
  The near-zero result is a property of the dataset as much as the pipeline: treatment
  in these TCGA cohorts was cytotoxic and endocrine protocol care chosen by diagnosis,
  not by sequenced gene, which `scripts/diagnose_concordance_dataset.py` shows
  independently. `scripts/detect_label_circularity.py` gates against a reintroduction.
  See [ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md](ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md).

- **The 100% TCGA coverage figure in Section 1.3 no longer reproduces.** Re-measured
  2026-08-12: 52/72 = 72.2% covered on the 100-case request (Tier 1 10, Tier 2 31,
  Tier 3 11, no recommendation 20) and 104/142 = 73.2% on the 200-case request
  (Tier 1 30, Tier 2 58, Tier 3 16, no recommendation 38). The two agree closely,
  which is what you would expect if the difference is definitional rather than
  cohort noise. The cause is a change in what counts as coverage, not a pipeline
  regression. The
  published figure counted the Tier 4 custom-design escalation path as covered, and that
  is how the 200-patient row reached 100% with 185 of 200 cases in "stage 2 escalation".
  Custom drug design now requires explicit user action, so `tier4_custom_drug()` is never
  invoked from the benchmark loop and `CUSTOM_DESIGN` is unreachable. Those cases report
  as "no recommendation" instead. The paper's number answered "did the system produce any
  output, including an offer to design something"; the current number answers "did the
  system find a drug". See [BENCHMARK.md](BENCHMARK.md).

- **The benchmark cohort is not pinned.** Patients are drawn live from cBioPortal, so the
  set differs between runs: on 2026-08-12, `--n 100` returned 72 cases and `--n 200`
  returned 142. Any exact
  coverage percentage quoted from this benchmark, including the paper's, is a reading
  taken on a date rather than a fixed score, and two runs differ in cohort as well as in
  pipeline.

- **Tier 2 oncology-relevance gate** (`api/services/oncology_atc.py`, merged in PR #81).
  Filters repurposing candidates on WHO ATC class, keeping L01 antineoplastic and L02
  endocrine therapy and dropping drugs positively classified as something else. It removed
  0 drugs on the 2026-08-12 benchmark cohort, because that benchmark's Tier 2 already
  requires a cancer-context match or trial backing and is therefore stricter than
  production's Tier 2. The drugs it was built to remove, cardiac glycosides and beta
  blockers seen in the concordance pilot, reach patients through the production path, not
  this one.

None of the above existed, in any form, when the preprint was posted on May 18, 2026.

---

## Section 4 — Known stale item (flagged only, not corrected here)

`README.md` currently leads with the older 24-case holdout result (Hit@3 = 1.000). The
preprint itself (Section 3.1) describes this smaller holdout as superseded by the 50-case
set documented in Section 1.2 above. `README.md` needs a follow-up correction to cite the
paper's actual 50-case figures (Hit@3 = 0.900, Standard P@3 = 0.508, etc.) instead of the
older 24-case number. **This document does not make that correction** — it is flagged here
as a separate, linked follow-up task only.
