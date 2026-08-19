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

> **Superseded the same day.** The table in this section was produced while the
> benchmark queried only Tier 1 and the Tier 2 path was dead locally, so its
> independent subset scored 1/14. The corrected figures are in "The benchmark was
> querying one tier" below. This section is kept for the reasoning, which still
> holds, not for its numbers.

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

*(Numbers above are the superseded Tier-1-only run. Corrected: contained 17 arms
at 70.6% exact and 100% class, independent 15 arms at 20.0% exact and 53.3%
class.)*
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

## The benchmark was querying one tier, and Tier 2 was dead locally

Resolved 2026-08-19. The figures at the top of this document are the corrected
ones. What follows is how they moved and why, because the first version of this
section drew a conclusion that was wrong.

`run_pipeline` called only `get_all_drugs_for_variant_live`, the OncoKB live API
plus the curated static table. It never called the Tier 2 repurposing path that
the TCGA concordance pilot calls. An independence audit then split the arms on
whether the assigned drug was already in the evidence table and found 7.1% exact
Top-3 on the ones that were not, which was read as the engine failing to
generalise. That subset had been constructed to exclude everything the only tier
being queried could answer.

Wiring Tier 2 in as a fallback changed nothing at first, which turned out to be a
second and larger defect.

**Two `ai` packages, and only one wins.** `api/ai/` holds `ranking.py`.
Repo-root `ai/` holds `diffdock/`, `alphamissense/` and `services/`. Both carried
an empty `__init__.py`, so each was a regular package and whichever appeared
first on `sys.path` shadowed the other entirely. `_query_repurposing_candidates`
imports `ai.diffdock.score` unguarded, so with `api/` first the entire Tier 2
path raised `ModuleNotFoundError` before doing any work.

The deployed container never hits this. `api/Dockerfile` does

    COPY api/. .
    COPY ai/. ./ai/

which merges both directories into one `/app/ai` on disk. Nothing outside the
container reproduces that, so every local script, benchmark and developer run got
a half-populated `ai` package, and the failure surfaced as a capability quietly
returning nothing rather than as an error.

Both empty `__init__.py` files are now removed, making `ai` a namespace package
that merges across `sys.path` the way the container merges it on disk.

### What it moved

| | Tier 1 only | Both tiers |
|---|---|---|
| Exact Top-3 | 13/32 (40.6%) | **15/32 (46.9%)** |
| Class Top-3 | 23/32 (71.9%) | **25/32 (78.1%)** |
| No recommendation | 2/32 | **0/32** |

Splitting the corrected run on whether the drug was already in the evidence
table:

| Subset | n | Exact Top-3 | Class Top-3 |
|---|---|---|---|
| Contained | 17 | 12 (70.6%) | 17 (100%) |
| Independent | 15 | 3 (20.0%) | 8 (53.3%) |

The independent subset moved from 7.1% to 20.0% exact and from 42.9% to 53.3%
class. The engine does reach past its own table; the benchmark was not letting
it. `X DDR2 dasatinib` went from no prediction at all to an exact hit.

20% exact on fifteen arms is still modest, and the honest reading is that the
engine finds the right drug family more often than the right drug when it has to
generalise. That is a real result rather than an artifact, which is more than
could be said of the 7.1%.

Reproduce the tier split: `python scripts/benchmark_nci_match.py --no-tier2`
reproduces the old Tier-1-only figures.

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

## Results (2026-08-19, both tiers)

| Metric | Value |
|---|---|
| Arms parsed from trial record | 38 |
| Arms scored | 32 |
| Out of scope | 6 |
| **Exact Top-3 concordance** | **15/32 = 46.9%** |
| **Class Top-3 concordance** | **25/32 = 78.1%** |
| No recommendation returned | 0/32 = 0.0% |

Earlier runs of this table read 12/32 and 22/32 on 2026-08-12, then 13/32 and
23/32, both with Tier 2 unreachable. `--no-tier2` reproduces the Tier-1-only
figures.

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
