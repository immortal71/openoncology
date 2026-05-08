# OpenOncology — Methods Overview

> **Status**: Research prototype. Methods have not been peer-reviewed.  
> **Version**: May 2026

## Table of Contents

1. [Overview](#overview)
2. [Ranking algorithm](#ranking-algorithm)
3. [Evidence sources](#evidence-sources)
4. [Benchmark methodology](#benchmark-methodology)
5. [Toxicity prediction](#toxicity-prediction)
6. [ADME prediction](#adme-prediction)
7. [System limitations](#system-limitations)
8. [References](#references)

---

## Overview

OpenOncology is an open-source research pipeline that integrates multiple publicly available evidence databases and computational tools to rank candidate repurposing drugs for a given somatic variant and cancer type. It is designed for:

- Research hypothesis generation (not clinical decision support yet maybe soon in future iterations)
- Educational exploration of precision oncology evidence frameworks
- Rapid prototyping of multi-source evidence fusion approaches

The pipeline ingests a VCF file, annotates variants, queries external databases, and returns a ranked list of drugs with confidence intervals and an audit trail.

---

## Ranking algorithm

### Input

A list of candidate drugs, each with zero or more of the following evidence fields:

| Field | Type | Source |
|---|---|---|
| `binding_score` | `float [0, 1]` | DiffDock molecular docking (GPU pipeline) |
| `association_score` | `float [0, 1]` | OpenTargets overall association score |
| `oncokb_level` | `str` | OncoKB evidence tier (LEVEL_1 → LEVEL_4, LEVEL_R1/R2) |
| `alphamissense_score` | `float [0, 1]` | AlphaMissense pathogenicity estimate |
| `max_phase` | `int [0, 4]` | Maximum clinical development phase |
| `civic_evidence_level` | `str` | CIViC evidence tier (A → E) |

### Step 1 — Normalise each source to `[0, 1]`

Each source is mapped to a normalised score via the following functions (defined in `api/ai/ranking_config.py`):

- **OncoKB**: `LEVEL_1=1.0, LEVEL_2=0.8, LEVEL_3A=0.6, LEVEL_3B=0.4, LEVEL_4=0.2, LEVEL_R1=0.1, LEVEL_R2=0.05`
- **CIViC**: `A=1.0, B=0.8, C=0.6, D=0.4, E=0.2`
- **ClinicalPhase**: `Approved=1.0, Phase3=0.7, Phase2=0.5, Phase1=0.3, Phase0/Unknown=0.1`
- **Binding** and **OpenTargets**: used directly (already in `[0, 1]`)
- **AlphaMissense**: used directly (pathogenicity score from Google DeepMind)

Missing values are treated as absent (not as 0.0) to avoid penalising drugs that simply lack a particular annotation.

### Step 2 — Weighted mean over present sources

$$\text{base\_score} = \frac{\sum_{i} w_i \cdot s_i}{\sum_{i} w_i \cdot \mathbf{1}[s_i \text{ present}]}$$

Default weights $(w_i)$:

| Source | Weight | Rationale |
|---|---|---|
| DiffDock binding | 0.25 | Direct binding affinity signal; highest clinical relevance when available |
| OncoKB | 0.25 | Curated clinical evidence; Level 1 = FDA-approved for this exact context |
| OpenTargets | 0.20 | Genome-wide genetic + somatic association evidence |
| AlphaMissense | 0.10 | Variant-level pathogenicity; informs disease relevance of the target |
| ClinicalPhase | 0.10 | Development stage proxy for safety and activity data availability |
| CIViC | 0.10 | Community-curated clinical variant interpretation |

> **Note**: These weights are research defaults chosen on evidence-tier principles. They have NOT been optimised against real-world outcome data. See the [ablation study section](#ablation-studies) for marginal contribution analysis.

### Step 3 — Post-hoc rules

Five rules are applied after the weighted mean:

1. **Resistance gate** (safety-critical)  
   Any drug with `oncokb_level ∈ {LEVEL_R1, LEVEL_R2}` has its `rank_score` hard-capped at 0.08, regardless of other evidence. This rule is non-negotiable — resistance designations must not be overridden by a strong DiffDock score.

2. **Safety penalty**  
   A penalty in `[0.0, 0.50]` is subtracted from `rank_score` based on:
   - Market-withdrawn drugs: −0.50
   - VERY_HIGH QSAR toxicity profile (de-novo only): −0.30
   - HIGH QSAR toxicity profile: −0.20
   - MODERATE: −0.10
   - Approved drugs are capped at −0.05 regardless of QSAR flags (FDA approval encodes clinical benefit/risk)

3. **Diversity penalty**  
   Drugs with only one non-trivial evidence source (`factor = 0.78`) receive a penalisation to reduce over-confident single-source rankings.

4. **Co-mutation / low-VAF attenuation**  
   Drugs receive additional downward adjustment when pathway-competing co-mutations are present, and very low VAF variants receive a conservative score discount.

5. **Robustness shaping (small calibration terms)**  
   Three low-magnitude terms improve tie-breaking among similar candidates while keeping high OncoKB evidence dominant:
   - **Conflict penalty**: subtract up to 0.12 based on cross-source score variance.
   - **Translational convergence bonus**: add up to 0.08 when OncoKB and CIViC both support the candidate.
   - **Multi-source support bonus**: add up to 0.04 for richer evidence coverage (2+ contributing sources).

   For safety, Level 1/2 OncoKB floor constraints are re-applied after robustness shaping so these terms do not suppress strong clinical evidence.

### Step 4 — Uncertainty quantification

A confidence interval is estimated from the number of missing sources:

$$\text{half\_width} = 0.07 \times |\text{missing sources}|$$

Capped at 0.40. Single-source drugs receive an additional aleatoric uncertainty of 0.12.

Confidence labels:
- HIGH: `rank_score ≥ 0.80`
- MEDIUM: `rank_score ≥ 0.50`
- LOW: `rank_score < 0.50`

All numeric thresholds are configurable via `api/ai/ranking_config.py`.

---

## Evidence sources

### OncoKB

- **URL**: https://oncokb.org
- **Coverage**: ~6000 variant-drug-tumour type entries (live API); static fallback covers ~120 Level 1/2/R1 entries
- **Access**: Free API token required from oncokb.org for live access
- **Limitations**: Coverage concentrated in common cancers (NSCLC, breast, CRC, melanoma). Rare tumours and paediatric cancers are underrepresented.

### OpenTargets

- **URL**: https://www.opentargets.org / GraphQL API
- **Coverage**: ~50,000 targets, 25,000+ diseases, genome-wide
- **Limitations**: Association scores are computed from heterogeneous evidence types with different reliability. High scores can reflect rare-variant genetics or expression correlations without mechanistic evidence for drug targeting.

### CIViC

- **URL**: https://civicdb.org
- **Coverage**: Community-curated; particularly strong for haematological malignancies and well-studied solid tumours
- **Limitations**: Coverage is uneven; many variants have low evidence ratings (C/D/E) that contribute little signal.

### AlphaMissense

- **Source**: Google DeepMind (Cheng et al., Science 2023)
- **Coverage**: All possible human missense variants (~71M)
- **Limitations**: Predicts pathogenicity of a missense change, not drug response. A pathogenic score indicates the variant may disrupt protein function; it does not imply a specific drug will work.

### DiffDock

- **Source**: MIT CSAIL (Stärk et al., ICLR 2023, arXiv:2210.01776)
- **Coverage**: Requires AlphaFold structure + SMILES of candidate drug
- **Limitations**: NOT run in the default demo. Requires GPU resources and takes ~30 minutes per target. Docking scores are not equivalent to experimental binding affinities; they are semi-quantitative poses from a generative model.

### ClinicalPhase

- **Source**: ChEMBL `max_phase` field
- **Coverage**: ~15,000 drugs with phase data
- **Limitations**: Phase reflects any indication, not the specific variant-cancer context being queried.

---

## Benchmark methodology

### Gold-standard case set

The benchmark uses a curated set of 200+ cases drawn from:

1. **OncoKB Level 1/2 cases** (~120): FDA-approved or standard-of-care drugs for specific variant-tumour combinations. Drugs with strong Level 1 evidence should rank in the top-3 positions.

2. **Extended cases** (~80): Covers Level 3/4 evidence, rare cancers, paediatric tumours, haematological malignancies, and cross-tumour agnostic approvals.

3. **VUS negative controls** (~40): Variants of uncertain significance or variants with no approved targeted therapy. The system must NOT over-claim Level 1/2 evidence for these cases. These test **specificity**, not sensitivity.

4. **Resistance cases** (~15): Known resistance mutations (e.g., EGFR T790M for erlotinib/gefitinib, ABL1 T315I for imatinib). The system must cap resistance drugs; the correct drug (e.g., osimertinib for T790M) should rank highly.

5. **Literature-sourced tumor board cases** (~30): Cases mined from published molecular tumor
   board reports in JCO Precision Oncology, Annals of Oncology, and Nature Medicine (see
   [holdout validation](#blind-holdout-validation-n50) below).

### Metrics

| Metric | Definition |
|---|---|
| Precision@K | Fraction of top-K ranked drugs that are known effective agents for the query variant |
| Hit@K | Whether at least one known drug appears in the top-K results |
| MRR | Mean Reciprocal Rank: average of 1/rank for the first known drug across cases |
| NDCG@5 | Normalised Discounted Cumulative Gain at K=5 |

### Running the benchmark

```python
from api.services.benchmark import run_benchmark_sync
report = run_benchmark_sync()
print(report.summary())
```

### Hard Clinical Benchmark (quality gate)

To avoid overfitting to easy single-drug cases, OpenOncology maintains a separate hard benchmark subset with:

- Multi-drug truth sets (`>= 2` known effective drugs)
- Low-purity and subclonal contexts
- Refractory/resistance settings
- Rare or tumour-context-sensitive cases
- Negative controls with expected empty output

The hard benchmark is evaluated with **Standard P@3** (`hits / 3`), not normalised P@3.

Policy targets:

- Standard P@3: `>= 0.65`
- Hit@3: `>= 0.90`
- False positives in negative controls: `0`

Run locally:

```bash
.venv\\Scripts\\python.exe scripts\\hard_benchmark_gate.py
```

This gate is also run in CI to prevent silent quality regressions.

### Blind Holdout Validation (n=50)

The blind holdout validation evaluates pipeline quality on cases that were never seen during
development. Cases are drawn from `ADDITIONAL_VALIDATION_CASES`, which now includes a dedicated
literature-sourced subset of 30 published tumor board cases.

#### Case sources

The 30 literature cases span three difficulty tiers:

| Tier | Count | Journals |
|---|---|---|
| L1_L2 (Level 1–2 evidence) | 12 | JCO Precision Oncology, Annals of Oncology |
| L3_L4 (Level 3–4 evidence) | 12 | JCO Precision Oncology, Annals of Oncology, Nature Medicine |
| VUS_NEG (negative controls) | 6 | JCO Precision Oncology, Nature Medicine |

Representative cases include:
- FGFR2 fusion intrahepatic cholangiocarcinoma → pemigatinib (JCO PO 2020, FIGHT-202)
- IDH1 R132H AML → ivosidenib (JCO PO 2019)
- HRAS Q61R HNSCC → tipifarnib (JCO PO 2021, AIM-HN trial)
- KMT2A::MLLT3 AML → revumenib (JCO PO 2023, AUGMENT-101)
- KRAS G12V GBM → negative control (no approved therapy; JCO PO 2022 actionability gap report)
- STK11 LOF NSCLC → negative control (resistance mechanism; Nature Medicine 2022)

#### Running the expanded holdout

```bash
# Default is now n=50
python scripts/blind_external_validation.py

# Explicit invocation with seed for reproducibility
python scripts/blind_external_validation.py --n-cases 50 --seed 11

# Produce only blind review packet (no scoring key)
python scripts/blind_external_validation.py --n-cases 50 --no-generate-diff
```

Outputs:
- `blind_review_packet.json` — de-identified case list for external clinical reviewer
- `blind_review_key_scoring.json` — expected labels + automated metric summary

#### Selection policy

Cases are sampled from `ADDITIONAL_VALIDATION_CASES` while excluding any overlap with
`HARD_CLINICAL_CASES`. Stratified quotas ensure the difficulty distribution matches the
full pool:

```
L1_L2 quota : round(n_cases × 0.45) = 23 for n=50
L3_L4 quota : round(n_cases × 0.35) = 18 for n=50
VUS_NEG quota: n_cases − L1_L2 − L3_L4  = 9 for n=50
```

### Real-world cBioPortal 100-case benchmark (May 2026)


In addition to the curated gold-standard benchmark, the pipeline was validated against **100 real de-identified TCGA patient mutation records** fetched from the public cBioPortal REST API. This test measures operational coverage and recommendation quality on genuine human genomic data — not synthetic or hand-crafted cases.

**Data source**: https://www.cbioportal.org (open-access TCGA de-identified somatic mutation data)  
**Script**: `scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json`

#### Tier distribution

| Tier | Count | Fraction |
|------|-------|---------|
| Tier 1 — FDA-approved drug matched | 36 | 36% |
| Tier 2 — Repurposing candidate | 64 | 64% |
| Tier 3 — Custom drug design | 0 | 0% |
| No recommendation | 0 | 0% |
| **Total covered** | **100** | **100%** |

#### Approval status of top recommendations

| Metric | Value |
|--------|-------|
| Top recommendation FDA-approved | 100 / 100 (100%) |
| Top-3 total FDA-approved entries | 284 |
| Top-3 non-FDA-approved entries | 0 |

#### Running the real-world benchmark

```bash
# Requires: httpx  (pip install httpx)
python scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json
```

Set `ONCOKB_API_TOKEN` (free at https://oncokb.org/account/register) for live Tier 1 matching.
Without the token the static ~120-entry fallback table is used; live token would increase Tier 1 fraction.

#### Interpretation caveats

- No clinical outcome data is available for these TCGA records; this is a coverage test, not an outcome validation.
- TCGA over-represents common cancers (NSCLC, colorectal, breast); real oncology practice case-mix differs.
- Tier 2 candidates are mechanistically supported but lack direct FDA indication for the specific mutation+cancer context.

### Ablation studies

The `run_ablation_study()` function evaluates the marginal contribution of each evidence source by setting its weight to 0.0 and redistributing weight equally across the remaining sources. A large negative ΔMRR when removing a source indicates that source is valuable.

```python
from api.services.benchmark import run_ablation_sync, LEVEL_1_CASES
report = run_ablation_sync(cases=LEVEL_1_CASES)
print(report.summary())
```

> **Important caveat**: Ablation on the current benchmark primarily tests the weighting scheme given the *data that exists*. If a source (e.g., DiffDock) is absent for most cases, its ablation delta will be near-zero — this reflects data absence, not that the source is uninformative when data is present.

---

## Toxicity prediction

Toxicity predictions use QSAR (Quantitative Structure-Activity Relationship) methods based on:

1. **Structural alerts (SMARTS patterns)**: Substructure matches against known toxic pharmacophores from the Kazius (Ames), Brenk (hepatotoxicity), Jamieson (CYP), and Baell & Holloway (PAINS) alert sets.

2. **Physicochemical thresholds**: Rule-based flags based on logP, molecular weight, PSA, and other Lipinski/Veber properties.

### Assays covered

| Assay | Method | Known performance |
|---|---|---|
| Ames mutagenicity | 14 Kazius SMARTS alerts | Sensitivity ~85%, Specificity ~66% on Kazius training set |
| hERG (QT prolongation) | 5 structural alerts + logP/MW heuristic | Specificity ~90% for HIGH confidence alerts |
| Hepatotoxicity (DILI) | Brenk alerts + MW/logP physicochemical | AUC ~0.71–0.76 on DILIst dataset |
| CYP inhibition | 13 structural alerts across 5 isoforms | Sensitivity 70–80% per isoform |
| PAINS | 8 Baell & Holloway filters | ~5–10% false-positive rate on approved drugs |

### SMILES enrichment

If a candidate drug lacks SMILES data, the pipeline attempts to fetch canonical SMILES from:
1. ChEMBL (primary, curated)
2. PubChem PUG REST (fallback)

Toxicity flags are severely limited without SMILES data.

### De-novo compound warnings

Compounds lacking a ChEMBL ID, PubChem CID, or approved status trigger an explicit de-novo warning (`DENOVO_WARNING` constant in `toxicity.py`). This warning is included in the `OffTargetLiabilityProfile` returned by `assess_off_target_liability()` and should be surfaced prominently to any user.

---

## ADME prediction

ADME (Absorption, Distribution, Metabolism, Excretion) predictions use physicochemical heuristics:

| Property | Method |
|---|---|
| Synthetic Accessibility (SA score) | RDKit SA score (Ertl & Schuffenhauer 2009) if RDKit available; complexity heuristic otherwise |
| BBB penetration | MW < 400, logP 1–4, PSA < 90, HBD ≤ 3 (Lipinski-derived) |
| P-gp substrate | MW > 400 + PSA > 100 (approximate) |
| Oral bioavailability | Rule of 5 (Lipinski 1997) + Veber rules |
| Metabolic stability (HLM) | logP/MW/rotatable bonds heuristic; not experimentally validated |
| Plasma protein binding (PPB) | logP-based heuristic; accuracy ±15% vs. experimental |
| Aqueous solubility | GSE model (Delaney 2004) approximation |

> All ADME predictions are estimates. Experimental validation is required before any in-vivo or clinical work.

---

## System limitations

The following limitations are also programmatically accessible via `get_system_limitations()` in `api/ai/ranking.py`:

1. **Binding scores absent in default demo**: DiffDock requires a GPU pipeline; `binding_score` is 0 for all drugs when not configured.
2. **OncoKB API not configured**: Falls back to ~120-entry static table. Live API has broader coverage.
3. **AlphaMissense scores may be absent**: If scores are not pre-loaded, the source contributes 0.
4. **QSAR-only toxicity**: Structural alerts are not validated QSAR models. Wet-lab confirmation is mandatory.
5. **Evidence weights are research defaults**: Not optimised against real-world outcome data.
6. **Benchmark coverage**: ~200 curated cases. Real-world precision oncology involves co-mutations, uncertain VAF, and conflicting evidence that is not well-tested.
7. **AlphaFold/DiffDock not in default demo**: Advanced AI binding predictions require separate configuration.

## Clinical reporting guardrails

Every oncologist report must explicitly state:

1. This is an experimental open-source tool.
2. It is not CLIA/CAP validated.
3. Standard P@3 on broad benchmark is approximately 0.50.
4. All recommendations require independent verification by the treating oncologist.

Patient-facing flow defaults to:

1. Simple patient letter first (plain-language, empathetic summary).
2. Explicit action to generate a separate doctor-facing report.

This separation is intentional to reduce patient confusion and prevent technical over-interpretation.

---

## References

- **OncoKB**: Chakravarty et al., JCO Precision Oncology 2017, PO.17.00011. https://oncokb.org
- **CIViC**: Griffith et al., Nature Genetics 2017. https://civicdb.org
- **OpenTargets**: Ochoa et al., Nucleic Acids Research 2023. https://www.opentargets.org
- **AlphaMissense**: Cheng et al., Science 2023. https://deepmind.google/technologies/alphamissense/
- **DiffDock**: Stärk et al., ICLR 2023, arXiv:2210.01776. https://arxiv.org/abs/2210.01776
- **AlphaFold**: Jumper et al., Nature 2021. https://alphafold.ebi.ac.uk
- **RDKit SA Score**: Ertl & Schuffenhauer, J. Cheminformatics 2009.
- **Ames SMARTS**: Kazius et al., J. Med. Chem. 2005.
- **Hepatotox SMARTS**: Brenk et al., ChemMedChem 2008.
- **PAINS**: Baell & Holloway, J. Med. Chem. 2010.
- **hERG alerts**: Jamieson et al., Drug Metab. Dispos. 2006.
- **Oral bioavailability**: Lipinski et al., Adv. Drug Deliv. Rev. 1997; Veber et al., J. Med. Chem. 2002.
- **Delaney solubility**: Delaney, J. Chem. Inf. Comput. Sci. 2004.
- **ChEMBL**: Mendez et al., Nucleic Acids Research 2019. https://www.ebi.ac.uk/chembl/
- **Chapman et al. (vemurafenib/BRAF)**: Chapman et al., NEJM 2011 — not directly cited in this document; listed here for completeness of BRAF V600E treatment history. This reference is unused in the current methods text.

### Tumor board case report sources (holdout literature cases)

- **FGFR2 fusion iCCA**: Abou-Alfa et al., NEJM 2020; Goyal et al., Lancet Oncol 2020. FIGHT-202 trial.
- **IDH1 R132H AML**: DiNardo et al., NEJM 2018. AG120-C-001 Phase 1/2.
- **PDGFRA D842V GIST / KIT D816V mastocytosis**: Heinrich et al., JCO PO 2020. NAVIGATOR trial.
- **HRAS Q61R HNSCC**: Ho et al., Cancer Cell 2021. AIM-HN Phase 2.
- **SMARCB1 LOF epithelioid sarcoma**: Gounder et al., JCO 2020. EZH-302 basket.
- **KMT2A rearrangement AML**: Issa et al., Nat Med 2023. AUGMENT-101. (Revumenib FDA-approved Nov 2024.)
- **ALK G1202R resistance NSCLC**: Shaw et al., NEJM 2017; Gainor et al., Cancer Discov 2016.
- **FGFR3 S249C urothelial**: Loriot et al., NEJM 2019. FIGHT-201 trial.
- **EGFR G719X NSCLC (atypical)**: Yang et al., Ann Oncol 2019. LUX-Lung 2/3/6 pooled analysis.

### End-to-end case illustration

See `docs/PATIENT_WALKTHROUGH.md` for a complete step-by-step walkthrough of a KRAS G12C NSCLC
case, showing VCF input through variant annotation, drug ranking, and the full Stage 2
precision-oncology brief that the pipeline produces for oncologist review.
