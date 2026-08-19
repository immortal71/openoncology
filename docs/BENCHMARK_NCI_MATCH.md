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

## How much of this is generalisation, and how much is reading our own table

Added 2026-08-19. `python scripts/audit_nci_match_independence.py`, artifact
`validation_results/nci_match_independence.json`.

The answer key is independent of anything OpenOncology produced, so this is not
the F5 defect. But independent-of-our-output is not independent-of-our-evidence:
NCI-MATCH arms and this repository's actionability table are both distillations
of the same clinical literature. If every arm the engine gets right is an arm
whose gene-drug pair was already in the table, the benchmark measures whether
the engine can read its own table and order the result.

Splitting the 32 scored arms on exactly that:

| Subset | n | Exact Top-3 | Class Top-3 |
|---|---|---|---|
| Contained — assigned drug already in the evidence table for that gene | 18 | 12 (66.7%) | 17 (94.4%) |
| Independent — assigned drug not in the table, so a hit came from the repurposing tiers | 14 | **1 (7.1%)** | 6 (42.9%) |
| Combined (the headline) | 32 | 13 (40.6%) | 23 (71.9%) |

**The headline is carried by the contained subset.** On arms whose drug the
engine did not already hold, exact Top-3 concordance is 1 in 14. *(Retracted:
see the correction above. The benchmark queries only the evidence table, so this
subset was defined by exclusion from the one tier being asked.)* The class
figure holds up better, 42.9%, which says the engine often reaches the right
drug family without reaching the right drug.

So the defensible claim from this benchmark is narrower than the headline:
*when a biomarker-drug pair is in the evidence base, the ranker surfaces it in
the top three most of the time.* Whether the engine generalises to pairs it does
not already hold is answered by the independent subset, and that answer is
currently close to no for exact matching.

**Two caveats that cut in opposite directions.** An arm reachable only through
gene-level fallback is counted as contained, which understates the independent
subset rather than flattering it. Against that, this run served every lookup
from the undated static table: OncoKB's public dump returned 401 throughout and
the degraded-evidence alarm fired on all 33 resolutions. With a current dump,
more arms would fall into the contained bucket, and the independent subset would
shrink further rather than improve.

Fourteen arms is an observation, not an estimate. The counts are given because
the percentages over that n are not worth much on their own.

---

## Correction: the benchmark never called the tier that generalises

The two sections below were written on 2026-08-19 and their conclusion was
wrong. It is left in place, with this correction above it, because deleting a
retracted reading hides the mistake instead of recording it.

`run_pipeline` in `scripts/benchmark_nci_match.py` calls only
`get_all_drugs_for_variant_live`, which is the OncoKB live API plus the curated
static table. It never calls the Tier 2 repurposing path, OpenTargets and DGIdb,
which the TCGA concordance pilot did call explicitly.

So the benchmark asks the evidence table a question, and the independence audit
below defined "independent" as *not in the evidence table*. A near-zero score on
that subset is close to circular in the opposite direction from F5: the subset
was constructed to exclude everything the only tier being queried could answer.
The engine has a generalisation path and the benchmark never invoked it.

`python scripts/diagnose_nci_match_tier2.py`, artifact
`validation_results/nci_match_tier2_diagnosis.json`, asks each missed arm
separately whether Tier 1 holds the drug, whether Tier 2 retrieves it, and
whether it is approved at all:

| Verdict | n | Arms |
|---|---|---|
| Reachable but not ranked. Tier 2 returns it as approved | **6** | ERBB2 afatinib, FGFR1 erdafitinib, TSC1 sapanisertib, DDR2 dasatinib, PTEN copanlisib (Z1G, Z1H) |
| Not retrieved by any tier. A real coverage gap | 4 | GNAQ trametinib, NF2 defactinib, FGFR3 AZD4547, BRCA1 adavosertib |
| Out of scope: investigational, deliberately not recommended | 3 | PIK3CA taselisib, PTEN GSK2636771, BRAF ulixertinib |

**Six of thirteen misses are drugs the engine already retrieves.** The benchmark
understates it. Three more are compounds it declines to recommend on purpose,
because suggesting an unapproved agent to a patient is not repurposing. The
genuine coverage gap is four arms, not thirteen.

The actionable defect is therefore in `benchmark_nci_match.py`, not in the
engine: the benchmark must invoke both tiers, as the TCGA pilot does, before any
generalisation claim can be made from it either way. Until it does, neither
40.6% nor 7.1% measures what it was read as measuring.

Two caveats on this correction. `sapanisertib` is reported as approved with a
phase 4 by OpenTargets, which does not match its regulatory status; approval
here is the service's opinion, not a regulatory determination, and the
"reachable" count may be one high. And `erdafitinib` shows as present in Tier 1
under a variant-free lookup while the independence audit placed it in the
independent bucket, so the two lookups disagree on containment and the split is
softer than a table implies.

## Would a bigger evidence base fix it?

The obvious response to a 7.1% independent subset is that the engine should hold
more evidence. `data/civic_evidence.tsv` is a 4 MB CIViC bulk export already in
this repository, used only for live per-variant lookups and never loaded into the
actionability table. Loading it was measured before it was attempted, because the
evidence table decides which drugs reach a patient's report and is the
highest-consequence thing in this codebase to edit on an intuition.

`python scripts/audit_civic_coverage_gain.py`, artifact
`validation_results/civic_coverage_gain.json`:

| | |
|---|---|
| CIViC rows | 4,854 |
| Predictive, supporting direction | 2,461 |
| Of those, evidence level A or B | 830 |
| Distinct gene-drug pairs | 487 across 159 genes |
| NCI-MATCH arms missed on exact match | 13 |
| **Arms CIViC A/B would make reachable** | **3** (ERBB2 afatinib, FGFR1 erdafitinib, GNAQ trametinib) |
| Arms still absent | 10 |

Only level A and B are counted. A is validated association and B is clinical
evidence; C, D and E are case study, preclinical and inferential, and loading
those as actionable would inflate what the system claims relative to what it
knows.

**The conclusion is not the one the premise suggested.** 487 pairs across 159
genes is a real expansion against a static table of 335 entries, and worth doing
on coverage grounds. But it closes 3 of the 13 measured misses. The
generalisation gap is not mostly an evidence-volume problem, so loading CIViC
would improve the table without fixing the thing that motivated loading it.

Coverage is also not correctness. A reachable pair is not a top-three
recommendation and not a right one, so the 3 is an upper bound on the gain and
the real figure can only come from loading the data and rerunning the benchmark.

---

## Why NCI-MATCH

Each NCI-MATCH subprotocol is an explicit, published, expert-committee decision of
the form **"patients with biomarker X receive drug Y."** The biomarker is the
eligibility criterion and it is fixed *before* the drug is assigned. That is the
same question OpenOncology answers, so it is a fair comparison.

### This is not the circular benchmark

`scripts/build_concordance_labels.py` used to contain a `DRUG_BIOMARKER_MAP` that
inferred each patient's gene **from the drug they were given** (patient received
vemurafenib → label records BRAF V600E). Asking the pipeline "which drug for BRAF
V600E?" then guarantees a match. That is the origin of the retracted **100%
class-adjusted (36/36)** figure, and it is why that figure must not be quoted as
evidence of accuracy. The map has been removed and the builder now joins
cBioPortal sequencing records to GDC treatment records on patient id;
`docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md` carries the rebuilt numbers.

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
| No recommendation returned | 4/32 = 12.5% |

> No-prediction fell from 5/32 to 4/32 when the BRCA1/2 truncating-variant fix
> landed (BRCA1 now returns PARP inhibitors instead of nothing). Concordance did
> **not** move: arm Z1I assigns adavosertib, a WEE1 inhibitor, so recommending a
> PARP inhibitor is correctly still scored a miss. A real coverage improvement
> that does not flatter this benchmark is the expected shape of an honest fix.

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
  reported separately and never merged. This is the most gameable part of the
  benchmark and it has already caught one real instance: PARP and WEE1 inhibitors
  were briefly grouped together, which silently turned the adavosertib arm from a
  miss into a hit as soon as BRCA started resolving. They are now separate groups
  (different targets; a PARP inhibitor is not a substitute for a WEE1 inhibitor)
  and the arm scores as a miss again. Treat any future edit to `DRUG_CLASSES` that
  raises the score as suspect until justified by shared mechanism alone.
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
