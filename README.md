<div align="center">

# OpenOncology

**Free AI-powered personalized cancer drug analysis — no insurance, no subscription, no gatekeeping.**

<p>
  <a href="https://github.com/immortal71/openoncology/stargazers"><img src="https://img.shields.io/github/stars/immortal71/openoncology?style=for-the-badge&logo=github&color=f59e0b&logoColor=white" alt="Stars"/></a>
  <a href="https://github.com/immortal71/openoncology/network/members"><img src="https://img.shields.io/github/forks/immortal71/openoncology?style=for-the-badge&logo=github&color=0ea5e9&logoColor=white" alt="Forks"/></a>
  <a href="https://github.com/immortal71/openoncology/issues"><img src="https://img.shields.io/github/issues/immortal71/openoncology?style=for-the-badge&color=ef4444&logo=github&logoColor=white" alt="Issues"/></a>
  <a href="https://github.com/immortal71/openoncology/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge" alt="MIT License"/></a>
</p>
<p>
  <img src="https://img.shields.io/badge/Python-3.11-3b82f6?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js 14"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/HIPAA-Compliant-6366f1?style=for-the-badge" alt="HIPAA Compliant"/>
  <img src="https://img.shields.io/badge/Benchmark%20P@3-0.817-22c55e?style=for-the-badge" alt="Benchmark P@3 0.817"/>
</p>

</div>

---

> **All drug rankings are sourced from FDA-approved evidence (OncoKB Levels 1–2). Oncologist review is required before any treatment decision. This software is not a licensed medical device.**

---

## What is OpenOncology?

OpenOncology is a free, open-source AI platform that analyses a patient's cancer mutation profile and returns ranked FDA-approved drugs, repurposing candidates, and — when no match exists — a custom drug discovery brief. Designed for patients and oncologists who cannot access expensive genomic advisory services. Self-hosted under MIT, no API key required for core functionality.

**Three-tier output:**
1. **FDA-approved targeted therapies** — OncoKB Level 1/2 with resistance gating
2. **Repurposing candidates** — approved drugs with mechanistic evidence for this mutation
3. **Custom discovery brief** — ChEMBL + AlphaFold leads when no approved match exists (v1: research tool only)

---

## Quick Start (3 commands)

```bash
git clone https://github.com/immortal71/openoncology.git
cd openoncology
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

**No Docker?** See [docs/SETUP.md](docs/SETUP.md) for local Python + Node.js setup, environment variables, and Windows-specific steps.

---

## Key Features

| Feature | Details |
|---------|---------|
| **FDA drug matching** | 294-entry curated evidence table · 74 actionable genes · OncoKB Levels 1–4 |
| **Resistance gating** | Blocks drugs with known resistance for the detected mutation (e.g. erlotinib blocked at EGFR T790M) |
| **Drug repurposing** | Off-label candidates scored by ChEMBL + OpenTargets + clinical phase + CIViC |
| **Cancer context** | Same mutation gets different evidence per tumour type (BRAF V600E melanoma ≠ CRC ≠ NSCLC) |
| **AI scoring** | AlphaMissense pathogenicity · DiffDock binding · composite weighted rank |
| **Combination therapy** | FDA-approved combination regimens detected (BRAF+MEK, CDK4/6+ER, etc.) |
| **Immunotherapy** | TMB-H, MSI-H/dMMR, HRD biomarker analysis |
| **HIPAA / GDPR** | Audit log on all PHI routes · Art.17 erasure · Art.20 export |
| **Benchmark** | Hard P@3 gate: 81 cases, P@3=0.817, Hit@3=100%, FP=0 |

---

## Benchmark

The hard clinical benchmark (`scripts/hard_benchmark_gate.py`) covers 81 cases:
73 sensitivity + 8 negative controls. All metrics computed honestly with the gate
script — no manual tuning, no cherry-picked cases.

| Metric | Value |
|--------|-------|
| Standard P@3 | **0.817** |
| Hit@3 | **100%** |
| False positives | **0** |
| Gate | **PASS** (threshold ≥ 0.65) |

```bash
python scripts/hard_benchmark_gate.py   # verify yourself
```

Full methodology: [docs/BENCHMARK_v0817_2026-05-29.md](docs/BENCHMARK_v0817_2026-05-29.md)

Blinded oncologist holdout (50 cases): Hit@3=0.900, FP=0, MRR=0.883
— published baseline from [doi:10.21203/rs.3.rs-9707913/v1](https://doi.org/10.21203/rs.3.rs-9707913/v1)

---

## Documentation

| Document | Contents |
|----------|---------|
| [docs/SETUP.md](docs/SETUP.md) | Full setup: Python, Node.js, Docker, env vars, troubleshooting, Windows |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System components, data flow, worker roles, database schema |
| [docs/DRUG_DECISION_LOGIC.md](docs/DRUG_DECISION_LOGIC.md) | FDA vs repurposed vs custom — three-tier decision tree |
| [docs/REPURPOSING_ALGORITHM.md](docs/REPURPOSING_ALGORITHM.md) | Repurposing scoring, comparison with DGIdb / DrugBank / OpenTargets |
| [docs/METHODS.md](docs/METHODS.md) | Full scientific methods |
| [docs/HIPAA_COMPLIANCE.md](docs/HIPAA_COMPLIANCE.md) | HIPAA §164 implementation details |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to add evidence, run benchmarks, submit PRs |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · React Query |
| Backend | FastAPI · SQLAlchemy 2 async · Celery · Redis |
| Database | PostgreSQL 16 · Alembic (12 tables) |
| Storage & Auth | MinIO (AES-256) · Keycloak OIDC/OAuth2 |
| AI / ML | AlphaMissense · AlphaFold Server · DiffDock · GPT-4o |
| Drug evidence | OncoKB · OpenTargets · ChEMBL · CIViC · COSMIC v3.1 |
| Genomics | Nextflow · BWA-MEM2 · GATK · OpenCRAVAT · GRCh38 |
| DevOps | Docker Compose · Kubernetes/Helm · Prometheus · GitHub Actions |

---

## Roadmap

| Phase | Status | Milestone |
|:-----:|:------:|:----------|
| 1–5 | ✅ | Infrastructure · AI pipeline · Marketplace · HIPAA/GDPR · Security CI |
| 5.6 | ✅ | Blinded oncologist holdout · Hit@3=0.900 · FP=0 · Hard benchmark gate |
| 5.7 | ✅ | P@3=0.817 · Repotrectinib (NTRK) · EGFR exon20 bug fix · Drug-tier API field |
| 6 | 🔜 | Multi-omics (RNA-seq, methylation) · Federated learning · Mobile app |
| v2 | 🔜 | De novo molecule generation · ADME/PK prediction · Custom drug synthesis planning |

---

## 📄 Cite This Work

[![DOI](https://img.shields.io/badge/DOI-10.21203%2Frs.3.rs--9707913%2Fv1-blue?style=flat-square)](https://doi.org/10.21203/rs.3.rs-9707913/v1)

> **Kharel, A.** (2026). *OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision Oncology.* Research Square. https://doi.org/10.21203/rs.3.rs-9707913/v1

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
  note      = {Preprint -- under review}
}
```

---

## ⚠️ Disclaimer

OpenOncology surfaces FDA-sourced evidence rankings to support expert clinical review. It is **not a licensed medical device** and has not been submitted for FDA clearance or CE marking. Drug rankings must be interpreted by a qualified oncologist. The authors provide this software under the MIT licence with no warranty.

---

<div align="center">

[⭐ Star](https://github.com/immortal71/openoncology) &nbsp;·&nbsp;
[🐛 Report a bug](https://github.com/immortal71/openoncology/issues/new?template=bug_report.md) &nbsp;·&nbsp;
[💬 Discussions](https://github.com/immortal71/openoncology/discussions) &nbsp;·&nbsp;
[📖 Full Setup](docs/SETUP.md) &nbsp;·&nbsp;
[📄 Methods](docs/METHODS.md)

</div>
