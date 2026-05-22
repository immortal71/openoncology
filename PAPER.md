# OpenOncology — Preprint Reference

[![DOI](https://img.shields.io/badge/DOI-10.21203%2Frs.3.rs--9707913%2Fv1-blue?style=flat-square)](https://doi.org/10.21203/rs.3.rs-9707913/v1)
[![Research Square](https://img.shields.io/badge/Preprint-Research%20Square-orange?style=flat-square)](https://www.researchsquare.com/article/rs-9707913/v1)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey?style=flat-square)](https://creativecommons.org/licenses/by/4.0/)

---

## Title

**OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision Oncology**

---

## Authors

| Name | Affiliation |
|:-----|:------------|
| Aashish Kharel | Independent Researcher |

---

## Publication Details

| Field | Value |
|:------|:------|
| **Type** | Preprint (under review) |
| **Server** | Research Square |
| **DOI** | [10.21203/rs.3.rs-9707913/v1](https://doi.org/10.21203/rs.3.rs-9707913/v1) |
| **URL** | https://www.researchsquare.com/article/rs-9707913/v1 |
| **Posted** | 18 May 2026 |
| **License** | CC BY 4.0 |

---

## Abstract

**Background**

Precision oncology depends on rapid, evidence-based matching of tumor variants to approved therapies. However, two compounding problems limit access for most patients worldwide: first, the interpretation infrastructure remains locked behind institutional subscriptions; second, even well-resourced precision oncology pipelines return empty outputs when no approved or repurposed drug exists for a patient's specific mutation — a complete dead-end that affects the majority of patients with rare or non-hotspot variants. Both problems are structural, not scientific.

**Methods**

We present OpenOncology, a fully open-source platform that solves both problems in sequence. Stage one performs a clinical-grade variant calling workflow (FastQC → BWA-MEM2 → GATK), pathogenicity scoring (AlphaMissense), protein structure prediction (AlphaFold Server), molecular docking (DiffDock), and drug ranking from a weighted composite of OncoKB actionability, OpenTargets evidence, COSMIC frequency, clinical trial phase, and binding confidence. AlphaFold Server and DiffDock are computationally intensive external services; throughput in production deployments is subject to rate limits and available hardware. Stage two — triggered when stage one finds no approved or repurposed match — executes a fully automated custom drug discovery workflow: it queries ChEMBL and OpenTargets for lead molecules against the patient's specific target, scores oral bioavailability via Lipinski Rule of Five, generates a mutation-specific AlphaFold protein structure, and assembles a manufacturer-ready discovery brief that pharmaceutical companies can bid on through an integrated marketplace. A crowdfunding module enables patients to raise resources for custom synthesis.

**Results**

Validation against a blinded 50-case oncologist holdout yielded Hit@3 = 0.900, Standard Precision@3 = 0.508 (ceiling: 0.625), Normalised Precision@3 = 0.817, Mean Reciprocal Rank = 0.883, and zero false-positive recommendations. The 50-case holdout included 12 Level 3–4 literature-sourced cases and 6 negative controls, representing a deliberately harder validation set than smaller prior holdouts; the metric profile reflects increased case difficulty. Stage two (custom drug discovery) validation is structural — discovery briefs are verified to contain real ChEMBL and OpenTargets records; clinical validation of lead molecule selection requires experimental binding assays outside the scope of this release. Equivalence-adjusted oncologist concordance reached 100% at both Top-1 and Top-3 across 36 actionable TCGA cases. TCGA benchmarks at 100 and 200 patients demonstrated 100% pipeline coverage with zero empty outputs — every patient received either an approved drug recommendation or a structured custom discovery brief.

**Conclusions**

OpenOncology is the first open-source precision oncology platform to provide a complete, safe escalation pathway from approved drug matching through to de novo custom drug discovery for patients with no existing therapeutic option. All code, benchmark scripts, and validation artifacts are publicly available at github.com/immortal71/openoncology under the MIT licence.

---

## BibTeX Citation

```bibtex
@misc{kharel2026openoncology,
  title     = {OpenOncology: An Open-Source Framework for Evidence-Based
               Drug Matching and De Novo Custom Drug Discovery in Precision Oncology},
  author    = {Kharel, Aashish},
  year      = {2026},
  month     = {05},
  publisher = {Research Square},
  doi       = {10.21203/rs.3.rs-9707913/v1},
  url       = {https://www.researchsquare.com/article/rs-9707913/v1},
  note      = {Preprint — under review}
}
```

---

## Plain-English Summary

The paper introduces **OpenOncology** as a solution to a systemic problem: most precision oncology tools either sit behind paywalls or simply give up when a patient's tumor mutation has no approved drug match. OpenOncology addresses this with a two-stage escalation design:

1. **Stage 1 — Drug Matching:** The platform ingests a patient's VCF file and biopsy report, runs clinical-grade variant calling, scores pathogenicity with AlphaMissense, models the mutant protein with AlphaFold, docks candidate drugs with DiffDock, and ranks them using a composite of OncoKB, OpenTargets, COSMIC, and clinical trial evidence.

2. **Stage 2 — Custom Drug Discovery (failsafe):** If Stage 1 finds no approved or repurposed match, instead of returning an empty result, the system automatically searches ChEMBL/OpenTargets for lead molecules, applies Lipinski filtering for oral bioavailability, and produces a structured "discovery brief" — a manufacturer-ready document that pharma companies can bid on via an integrated marketplace, with crowdfunding to help patients fund synthesis.

The paper validates this pipeline against a **blinded 50-case oncologist holdout** and real-world **TCGA cohorts at 100 and 200 patients**, demonstrating 100% coverage (zero empty outputs) and strong concordance with clinician recommendations.

---

## Codebase-to-Paper Mapping

| Paper Section | Codebase Location | Description |
|:--------------|:------------------|:------------|
| **Stage 1: Variant calling pipeline** | `pipeline/` | Nextflow workflow — FastQC → BWA-MEM2 → GATK |
| **Stage 1: AlphaMissense pathogenicity** | `ai/alphamissense/` | Variant pathogenicity scoring service |
| **Stage 1: DiffDock molecular docking** | `ai/diffdock/` | Protein–ligand docking integration |
| **Stage 1: Drug ranking engine** | `api/services/` | Composite ranking (OncoKB + OpenTargets + COSMIC + trial phase + binding confidence) |
| **Stage 2: Custom drug discovery** | `ai/repurposing/` | ChEMBL/OpenTargets querying, Lipinski scoring, AlphaFold structure generation |
| **Stage 2: Discovery brief & marketplace** | `api/routes/marketplace.py`, `api/routes/pharma_admin.py` | Manufacturer bidding API and campaign management |
| **Crowdfunding module** | `api/routes/campaign.py` | Patient fundraising for custom synthesis |
| **Validation scripts** | `scripts/` | Benchmark, concordance, and blind-review tooling |
| **Validation artifacts** | `artifacts/`, `validation_results/` | Raw outputs from holdout and TCGA benchmarks |
| **API / data layer** | `api/` | FastAPI backend, PostgreSQL models, async workers |
| **Frontend** | `web/` | Next.js patient and clinician interface |
| **Infrastructure** | `infra/` | Kubernetes, Prometheus, Helm charts, ZAP security scanning |

---

## Version Note

> This preprint documents **OpenOncology v2**, which is the current version of this repository. The two-stage escalation design, marketplace integration, crowdfunding module, and blinded 50-case oncologist holdout validation described in the paper are all implemented in the code on the `main` branch.

---

## Setup Instructions

For installation, local development, Docker deployment, and API usage see **[README.md](README.md)**.
