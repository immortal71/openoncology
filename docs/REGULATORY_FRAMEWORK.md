# Regulatory & Ethical Framework — OpenOncology

> **Disclaimer**: This document is a technical framework overview.  
> It does not constitute legal advice. Engage qualified regulatory counsel,  
> a bioethics board, and an IRB before any clinical use or real patient data.

---

## 1. Intended Use Statement

OpenOncology is a **clinical decision support tool** (CDSS) intended exclusively
for use by licensed oncologists and molecular pathologists to assist in the
interpretation of somatic genomic data and drug repurposing hypothesis generation.

**OpenOncology does NOT:**
- Diagnose cancer
- Prescribe or recommend treatments to patients directly
- Replace clinical judgement or the treating physician
- Manufacture or procure drugs
- Constitute a medical device under current intended use

**OpenOncology DOES:**
- Annotate somatic variants against evidence databases (OncoKB, CIViC, COSMIC)
- Rank repurposed drug hypotheses for oncologist review
- Provide computational ADME/toxicity signals for de-novo discovery briefs
- Generate evidence-cited summaries for oncologist interpretation

All outputs must be reviewed by a licensed oncologist before informing any
clinical decision. The platform explicitly labels all outputs as
"Investigational — For Research Use Only" until prospective clinical validation
is complete.

---

## 2. Regulatory Classification & Pathway

### 2.1 Current Status (Research Use Only)

The platform currently operates as **Research Use Only (RUO)** software under:
- **EU MDR 2017/745 Article 2(1)**: Excluded from device classification when
  used exclusively for research and scientific purposes.
- **FDA 21 CFR Part 820** / FD&C Act: Exempt from 510(k) / De Novo while in
  research mode, provided no clinical decisions are driven by outputs.

### 2.2 Path to IVD / SaMD Classification

To deploy clinically, the platform would require:

| Jurisdiction | Pathway | Classification | Notes |
|---|---|---|---|
| USA | FDA De Novo or 510(k) | SaMD Class II | Predicate: Tempus xT, Foundation One CDx (Class III if novel claims) |
| EU | CE Mark under EU IVD-R (2022/2024) | Class C or D IVD | Companion diagnostic: Class D |
| UK | MHRA UKCA | IVD Class C | Post-Brexit alignment with EU IVD-R |
| Canada | Health Canada SaMD | Class III MD | Drug-treatment matching |

**De Novo pathway triggers**: No FDA-cleared predicate with equivalent
variant-to-repurposed-drug ranking claim. Plan for De Novo submission with
clinical validation study data.

### 2.3 Companion Diagnostic Pathway (if drug-specific)

If the platform is used to select patients for a specific investigational drug,
it becomes a companion diagnostic (CDx) requiring:
- FDA PMA (Class III) or De Novo with the drug NDA/BLA
- Locked algorithm version with change-control SOP
  - **Partly in place.** `services/algorithm_version.py` computes a
    deterministic fingerprint over every input that can reorder drugs for fixed
    evidence: the ranking configuration, the candidate-pool policy, the CIViC
    supplement flag and the degraded-evidence policy. It is stamped onto each
    result at production time (`results.algorithm_version`, migration `0016`),
    so a recommendation names the rules that produced it rather than the rules
    in force when someone reads it.
  - `ALGORITHM_VERSION` is a semantic version moved by hand. The fingerprint
    moves on its own, and a test fails when the two disagree, so a behaviour
    change cannot land quietly. That is the change-control mechanism: code
    cannot lock an algorithm, it can only make a change impossible to make
    without a person noticing.
  - The fingerprint deliberately excludes the evidence table's contents. That
    identity belongs to `results.evidence_provenance`; folding it in would make
    the algorithm version churn on every OncoKB refresh and answer neither
    question well.
  - **Still missing for a submission:** a written SOP naming who approves a
    version change and on what evidence, and retention of superseded versions.
    The mechanism exists; the procedure around it does not.
- Clinical validity study (≥200 patient retrospective + prospective cohort)

---

## 3. Clinical Validation Requirements (Pre-Deployment)

The following validation milestones must be met before any oncologist uses
outputs to inform real patient treatment decisions:

### 3.1 Analytical Validation

Measured 2026-08-13. Every figure below is reproducible from a script in
`scripts/`, and each script prints what its number cannot support alongside what
it can. Read the "what it does not establish" column before quoting any of them.

| Test | Target | Status | Measured | What it does not establish |
|---|---|---|---|---|
| Variant calling accuracy (SNV/indel) vs. orthogonal WGS | Sensitivity ≥ 99%, PPV ≥ 95% | ⬜ Not completed | not run | Everything downstream is conditioned on this and it is unmeasured |
| AlphaMissense score concordance with ClinVar pathogenicity | Concordance ≥ 90% on BRCA1/2 benchmarks | ✅ Pass | **92.13% balanced accuracy** (n=1,471) | Missense only; BRCA1/2 only |
| Drug ranking Precision@3 vs. OncoKB L1/L2 | ≥ 0.60 | ⚠️ Pass, with leakage | **0.7247** (n=431) | 94.5% of gold cases are self-graded; this measures ranking, not evidence correctness |
| FFPE artefact detection sensitivity | ≥ 80% on FFPE-spiked samples | ⚠️ Pass, simulated | **100%** sensitivity, 0% false positive | Spike-in simulation, not paired FFPE/fresh-frozen tissue |

**AlphaMissense vs ClinVar** (`scripts/validate_alphamissense_clinvar.py`,
result in `validation_results/alphamissense_clinvar_concordance.json`).
1,471 BRCA1/BRCA2 missense variants with a ClinVar assertion at "criteria
provided" or better, 325 pathogenic and 1,146 benign, every one of them matched
to an AlphaMissense score. Sensitivity 88.78%, specificity 95.47%, balanced
accuracy 92.13%. BRCA1 92.6%, BRCA2 91.38%. Restricted to expert-panel and
practice-guideline assertions (n=396) balanced accuracy is 95.56%.

The gate text says "concordance ≥ 90%" without specifying the metric, and the
choice matters, so all three readings are reported: raw agreement counting
AlphaMissense's `ambiguous` class as wrong is **89.06%**, which fails;
excluding ambiguous it is **93.97%**; balanced accuracy is **92.13%**. Balanced
accuracy is gated on because the set is 3.5:1 benign, so a raw figure is
dominated by the majority class. The failing reading is recorded here rather
than dropped.

The two sources are genuinely independent: AlphaMissense is a published
predictor (Cheng et al., Science 2023) and ClinVar assertions are submitted by
clinical laboratories.

**Drug ranking Precision@3** (`scripts/validate_ranking_precision.py`, result in
`validation_results/ranking_precision.json`). Precision@1 0.868, Precision@3
0.7247, MRR 0.917 over 431 gold cases that produce a ranking.

This number is weaker than it looks and the script says so. 94.5% of judgeable
gold cases have their expected drugs already contained in the evidence table
being graded, so for those the metric asks whether the ranker can order its own
table, not whether the table is right. Split out: 0.7288 on the contained subset
(n=415), 0.6296 on the independent subset (n=24). The independent subset also
clears the threshold, but 24 cases is not a robust estimate.

**FFPE artefact detection** (`scripts/validate_ffpe_detection.py`, result in
`validation_results/ffpe_detection_sensitivity.json`). 100% detection at every
artefact burden from 10% upward, 0% false positives on clean samples, across 50
simulated samples per burden level built on 314 real variant coordinates from
`samples/real/`.

Saturated, and that is a property of the simulation as much as the detector:
artefact and somatic VAF are drawn from non-overlapping bands, while real
subclonal somatic variants sit inside the artefact VAF range. Read it as an
upper bound. The high-confidence threshold, which only saturates above 60%
burden, is what shows the score scale is not degenerate.

**Variant calling accuracy** remains unmeasured, and it is the most consequential
gap in this table. Every recommendation the system makes is conditioned on the
variant call being correct, so an unbounded error rate here bounds nothing
downstream. It cannot be measured on a developer workstation: it needs the
Nextflow pipeline in `pipeline/main.nf` with `bwa-mem2`, `gatk`, `samtools` and
`fastqc` available, a reference genome, and a truth-set sample such as a Genome
in a Bottle reference material with its high-confidence call regions.

The instrument for it now exists even though the measurement does not.
`scripts/validate_variant_calling.py` compares a query VCF against the GIAB
HG002 v4.2.1 GRCh38 benchmark inside NIST's high-confidence regions and reports
sensitivity, PPV and F1 split into SNVs and indels. Point it at a VCF from
`pipeline/main.nf` and the gate is answered; there is no remaining design work
between here and the number, only a machine with the toolchain on it.

Run on 2026-08-19 in its `--via-parser` mode, which holds the caller constant at
perfect and measures only the production ingestion path, it reported 100%
sensitivity and PPV over 83,325 GIAB chr20 variants (71,387 SNV, 11,938 indel).
**That figure is not this gate and is close to vacuous on its own.** Both sides
of the comparison derive from the same file, and of the three ingestion
behaviours the score appears to endorse, chr20 exercises exactly one: it
contains 953 multi-allelic records, so the F8 splitting path ran on real data,
while every record is `PASS` and none are malformed, so the F7 rejected-call
path and the malformed-record guards were never executed. The script prints and
records that breakdown under `path_coverage`. What the run supports is narrow:
the ingestion path is lossless on 83,325 real variants including 953
multi-allelic sites, and two independently written parsers agree on all of
them. It bounds ingestion loss and measures no caller.

### 3.2 Clinical Validation (Prospective)

| Study | Design | Sample Size | Status |
|---|---|---|---|
| Retrospective concordance | Compare drug rankings to MTB decisions in 100 real cases | n ≥ 100 | ⬜ Planned |
| Prospective pilot | IRB-approved pilot at one partner institution | n ≥ 50 | ⬜ Not started |
| Multi-site clinical utility | Oncologist survey + patient outcome tracking | n ≥ 500 | ⬜ Not started |

### 3.3 Performance Benchmarking vs. Commercial Platforms

Before clinical deployment, benchmark against:
- **Tempus xT** — variant-to-treatment matching on identical sample set
- **Foundation Medicine CDx** — companion diagnostic concordance
- **Caris Molecular Intelligence** — TMB + MSI concordance
- **SOPHiA DDM** — bioinformatics pipeline concordance
- **DepMap** — cell line drug sensitivity concordance

---

## 4. Custom Molecule / De Novo Discovery Safety Gates

The custom drug discovery feature generates **computational discovery briefs**
for synthesis by licensed pharma partners. The following safety gates are
implemented in `api/services/drug_discovery.py` and `api/services/toxicity.py`:

### 4.1 In-Silico Safety Panel (Implemented)

| Assay | Method | Action on Flag |
|---|---|---|
| hERG channel blocking | SMARTS + logP heuristic | HIGH → synthesis block |
| Ames mutagenicity | Kazius/Brenk SMARTS | HIGH → synthesis block |
| Hepatotoxicity | Brenk structural alerts | HIGH → warn; MEDIUM → flag |
| CYP inhibition | SMARTS panel (5 isoforms) | Flag; assess DDI risk |
| PAINS filters | Baell/Holloway SMARTS | Deprioritise candidate |
| Synthetic accessibility | SA score heuristic | DIFFICULT/VERY_DIFFICULT → warn |
| ADME (oral F%, t½) | QSAR heuristics | LOW BCS class → formulation review |

### 4.2 Required Wet-Lab Validation Before Synthesis

All de-novo candidates MUST undergo these before any synthesis proposal
is forwarded to a medicinal chemistry team:

1. **hERG patch-clamp assay** (IQ CSRC standardised protocol)
2. **Ames test** (OECD TG 471)
3. **HLM metabolic stability** (LC-MS/MS)
4. **Caco-2 permeability** (efflux ratio)
5. **in vitro cytotoxicity panel** (HepG2, MCF10A counter-screen)
6. **Selectivity profiling** vs. full kinase panel (Eurofins DiscoverX or equivalent)

### 4.3 Prohibited Actions

The platform explicitly prohibits and technically prevents:
- Forwarding any de-novo brief to synthesis without safety gate PASS
- Presenting de-novo molecules directly to patients or in clinical records
- Claiming clinical efficacy for any computational-only drug candidate
- Using the platform to select patients for unapproved drugs outside an IND

---

## 5. Consent, Privacy & Data Governance

### 5.1 HIPAA (USA)

- All PHI is encrypted at rest (AES-256) and in transit (TLS 1.3)
- Business Associate Agreements (BAAs) required with: AWS/GCP, Resend, Keycloak
- Minimum-necessary data access enforced via Keycloak RBAC
- Audit log for all PHI access (see `api/middleware/audit.py`)
- Patient right-of-deletion implemented (see `api/workers/gdpr_worker.py`)

### 5.2 GDPR (EU / UK)

| Requirement | Status |
|---|---|
| Lawful basis documented (research consent / legitimate interest) | ⬜ Pending legal review |
| Data Processing Agreement (DPA) with sub-processors | ⬜ Draft ready |
| Data subject access request (DSAR) endpoint | ✅ `GET /gdpr/request` |
| Right to erasure | ✅ `api/workers/gdpr_worker.py` |
| Data retention policy (max 5 years for research data) | ⬜ Policy document needed |
| Privacy notice for patients | ⬜ Draft needed |
| DPIA (Data Protection Impact Assessment) | ⬜ Required before clinical pilot |

### 5.3 Research Consent Requirements

For any research use involving real patient data:
- **IRB / Ethics Committee approval** required at each institution
- Written informed consent from each patient (or waiver if retrospective/de-identified)
- Consent form must describe: genomic sequencing, AI analysis, data sharing with pharma marketplace
- Participants must be informed of the investigational nature of all AI outputs

---

## 6. Liability & Indemnification Framework

### 6.1 Disclaimers (Implemented in UI and API)

Every API response includes:
```json
{
  "disclaimer": "For Research Use Only. Not for clinical decision-making without
                 oncologist review. All drug candidates are computational hypotheses
                 requiring wet-lab validation."
}
```

Every de-novo drug candidate includes:
```json
{
  "disclaimer": "Computational design proposal for medicinal-chemistry triage only;
                 requires synthesis and wet-lab validation."
}
```

### 6.2 Contractual Protections Required

Before allowing any oncologist or institution to use the platform:
1. **Master Service Agreement (MSA)** with indemnification clause
2. **Clinical Terms of Use** requiring oncologist sign-off on intended use
3. **Pharma Marketplace Terms** — explicitly prohibiting pharma from using
   patient data outside the agreed scope
4. **Product Liability Insurance** — minimum USD 10M per occurrence (clinical AI)

### 6.3 Crowdfunding / Pharma Marketplace Regulatory Note

The pharma bidding marketplace feature has additional regulatory implications:
- **SEC Regulation Crowdfunding** (USA): Research crowdfunding for drug
  development may trigger securities law requirements
- **FDA Off-label concerns**: The marketplace must not facilitate procurement
  of unapproved drugs for patient use
- **FTC / AG scrutiny**: Patient data monetisation in healthcare is under
  increasing regulatory scrutiny — obtain dedicated legal opinion

---

## 7. Clinical Oversight Requirements

Before any patient-facing deployment:

| Role | Requirement | Status |
|---|---|---|
| Medical Director | Licensed oncologist must review all clinical content | ⬜ Not appointed |
| Pathologist / Lab Director | Oversee sequencing QC and variant calling | ⬜ Not contracted |
| Bioethics Advisor | Review AI fairness, equity, and harm mitigation | ⬜ Not contracted |
| Data Protection Officer (DPO) | GDPR Article 37 requirement for EU operations | ⬜ Not appointed |
| IRB / Ethics Committee | Before any research involving real patient samples | ⬜ Not initiated |

---

## 8. Algorithm Transparency & Explainability

### 8.1 Implemented

- Every drug ranking includes a `rank_score` with confidence interval
  (`rank_score_ci_low`, `rank_score_ci_high`) and `evidence_completeness`
- `missing_sources` field lists which evidence sources were unavailable
- `confidence_level` (HIGH/MEDIUM/LOW) based on evidence completeness
- LLM summary cites the gene, oncokb level, and evidence databases
- FFPE and tumour purity warnings surfaced to end user before analysis

### 8.2 Required Before Clinical Use

- Rationale document for each scoring weight (DiffDock 30%, OpenTargets 25%, etc.)
- Independent statistical review of weighting methodology
- Bias assessment: performance by cancer type, ethnicity, sex, age
- Minimum evidence threshold below which no recommendation is made
  (e.g., if evidence_completeness < 0.4 → output "Insufficient evidence")

---

## 9. Known Limitations (Required Disclosure)

The following limitations MUST be disclosed to any clinical user:

1. **No prospective clinical validation**: Rankings are based on in-silico
   evidence. No patient outcome data has been used to validate effectiveness.
2. **Limited gene coverage**: AlphaMissense scoring covers ~120 oncogenes
   from static map; novel genes use live UniProt fallback which may be slower.
3. **No multi-omics integration in production pipeline**: RNA-seq module
   (`api/services/rnaseq.py`) is implemented but not yet wired into the
   Nextflow pipeline. DNA-only analysis is the current default.
4. **De-novo molecule safety is computational only**: hERG/Ames predictions
   are QSAR-based. Wet-lab confirmation is mandatory before synthesis.
5. **Cost and scalability**: AlphaFold3 + DiffDock runs cost ~$2–10 per
   patient at scale. Cost model for low-income settings not yet defined.
6. **Drug repurposing scope**: Only covers approved/clinical-stage drugs
   in OpenTargets/ChEMBL databases as of the last data update.

---

*Last updated: May 2026 — review required quarterly and before each major release.*
