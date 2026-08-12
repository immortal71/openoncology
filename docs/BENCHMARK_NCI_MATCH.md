# NCI-MATCH Arm Concordance Benchmark

**Run:** `python scripts/benchmark_nci_match.py`
**Artifact:** `validation_results/nci_match_concordance.json`
**Answer key:** NCI-MATCH (EAY131, `NCT02465060`), fetched live from ClinicalTrials.gov

This benchmark exists to answer one question the TCGA concordance pilot could not:
**when the biomarker genuinely drove the treatment decision, does OpenOncology pick
the same drug the experts picked?**

---

## Why a new benchmark was needed

The 2026-07-28 pilot (`docs/REAL_PATIENT_CONCORDANCE_PILOT_2026-07-28.md`) scored
**15.1% exact Top-3** against real TCGA oncologist prescriptions. That number is
real and is not withdrawn. But it is measured against an answer key where the
sequenced gene did not select the drug.

Measured directly from that pilot's answer key, without reference to anything
OpenOncology produced:

| Observation | Value |
|---|---|
| Sunitinib in TCGA-KIRC | 20 patients, spanning **16 different** sequenced genes |
| Bevacizumab in TCGA-KIRC | 13 patients, 8 genes |
| Sorafenib in TCGA-KIRC | 12 patients, 9 genes |
| TCGA-PRAD | top 5 drugs cover **10/10** patients |
| local_sample cohort | top 5 drugs cover **13/14** patients |

Those patients did not share a gene. They shared a diagnosis. Reproducing that
prescribing pattern would require emitting sunitinib for 16 unrelated genes —
that is, ignoring the gene, which is the one thing this engine must not do.

So the 15.1% measures *"does a gene-targeted engine reproduce era standard-of-care
protocol prescribing?"* — and the answer, correctly, is no. It does not measure
whether the engine picks the right targeted drug when a target exists.

Reproduce that diagnosis: `python scripts/diagnose_concordance_dataset.py`

---

## Why NCI-MATCH

Each NCI-MATCH subprotocol is an explicit, published, expert-committee decision of
the form **"patients with biomarker X receive drug Y."** The biomarker is the
eligibility criterion and it is fixed *before* the drug is assigned. That is the
same question OpenOncology answers, so it is a fair comparison.

### This is not the circular benchmark

`scripts/build_concordance_labels.py` contains a `DRUG_BIOMARKER_MAP` that infers
each patient's gene **from the drug they were given** (patient received
vemurafenib → label records BRAF V600E). Asking the pipeline "which drug for BRAF
V600E?" then guarantees a match. That is the origin of the **100% class-adjusted
(36/36)** figure in `docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md`, and it is why
that figure must not be quoted as evidence of accuracy.

This benchmark avoids that in three specific ways:

1. Arm definitions are fetched from ClinicalTrials.gov and parsed mechanically.
   No arm is included or excluded based on what OpenOncology returns.
2. Where an arm names a specific variant (`BRAF V600E`, `EGFR T790M`), that exact
   variant is used.
3. Where an arm names only a generic alteration (`PIK3CA mutation`), the variant is
   chosen **by real-world prevalence** — the most frequent protein change for that
   gene in cBioPortal / MSK-IMPACT (n≈10k sequenced patients), cached in
   `validation_results/hotspot_cache.json`. Prevalence is independent of any drug
   and of this repo's evidence table. Hand-picking a variant known to resolve would
   have been gaming; picking the one real patients most often carry is not.

That prevalence rule is not uniformly favourable, which is the point: it moved arm B
(ERBB2) from EXACT to MISS while moving arms A, I, Z1A, Z1F, Z1H into hits.

---

## Results (2026-08-12)

| Metric | Value |
|---|---|
| Arms parsed from trial record | 38 |
| Arms scored | 32 |
| Out of scope | 6 |
| **Exact Top-3 concordance** | **12/32 = 37.5%** |
| **Class Top-3 concordance** | **22/32 = 68.8%** |
| No recommendation returned | 5/32 = 15.6% |

Out of scope: 2 arms keyed on protein expression/IHC rather than a DNA variant
(`PTEN expression`, `MLH1/MSH2 loss by IHC`, `LAG-3 expression`), and 4 whose arm
text did not yield a parseable gene + drug pair. These are listed explicitly in the
script output rather than silently dropped.

### The exact-match ceiling is 75%, not 100%

NCI-MATCH is a **trial**, so many arms assign investigational agents that are not
FDA-approved and that an approved-drug recommender structurally cannot emit:

| Arm | Assigned agent | Result |
|---|---|---|
| I | taselisib | CLASS |
| M | sapanisertib | CLASS |
| P | GSK2636771 | miss |
| U | defactinib | miss |
| W | AZD4547 | miss |
| Z1I | adavosertib | miss |
| Z1K | ipatasertib | EXACT |
| Z1L | ulixertinib | miss |

**8 of 32 arms (25%) assign a non-approved agent.** Exact-match is therefore capped
at 24/32 = 75%. Read 37.5% against that ceiling, not against 100%. Class-level
concordance (68.8%) is the more meaningful figure here, because it credits
recommending an approved drug of the same mechanism as the trial's investigational
one — which is the clinically actionable answer for a patient not enrolled in the trial.

---

## How the three benchmarks relate

| Benchmark | Answer key | Was treatment biomarker-driven? | Score |
|---|---|---|---|
| TCGA concordance pilot | Real TCGA prescriptions | **No** — era protocol care | 15.1% exact Top-3 |
| **NCI-MATCH arms (this)** | Expert trial assignment | **Yes** — biomarker is the eligibility rule | **37.5% exact / 68.8% class** |
| Blinded 50-case holdout | Tumour-board literature | **Yes** | 0.900 Hit@3 |

The ordering is the finding: concordance rises with how biomarker-driven the answer
key is. That is consistent with the engine working as designed and the 15.1% being a
property of the TCGA dataset rather than of the ranking algorithm.

These three numbers use **different metrics on different case mixes and are not
directly comparable to each other.** Do not average them or quote one as a
replacement for another.

---

## Limitations — read before quoting any number here

- **Shared provenance.** NCI-MATCH arm assignments and this repo's OncoKB-derived
  evidence table are both built from the same body of published actionability
  literature. Agreement is therefore expected. A good score shows the evidence table
  correctly **encodes expert consensus** — it is *not* evidence of independent
  discovery, and not a validation of novel biology.
- **No patient outcomes.** This measures drug-assignment agreement only. It says
  nothing about whether any patient benefited. It is not a prospective clinical
  endpoint.
- **n = 32 arms.** Small. No confidence intervals computed.
- **One variant per arm.** Generic arms are represented by their single most
  prevalent variant; a different representative could move individual arms.
- **Gene families.** Arms naming a family (`FGFR amplification`) are expanded to
  members (FGFR1/2/3) and the first that resolves is used.
- **Class-equivalence groups are hand-authored** (`DRUG_CLASSES` in the script),
  using the same grouping rationale as
  `docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md`. Exact and class figures are always
  reported separately and never merged.
- Arm W scores `miss` partly on a string-formatting artifact: the assigned agent is
  recorded as `"FGFR Inhibitor AZD4547"`, which does not normalise onto the
  `azd4547` class member. Left uncorrected rather than special-cased.

---

## Integrity rules (same as `docs/BENCHMARK.md`)

- Numbers here are copied from `validation_results/nci_match_concordance.json`. Never
  edit them to match a desired result — rerun and copy what it prints.
- Never add, drop, or re-map an arm after seeing whether it scores as a hit.
- Never expand `DRUG_CLASSES` to convert a specific miss into a hit. Class groups must
  be defensible by shared mechanism, decided independently of any arm's outcome.
