# System Architecture — OpenOncology

---

## High-level overview

```
Patient submits sample (VCF / biopsy report)
          │
          ▼
  ┌──────────────┐
  │  Next.js UI  │  ← browser
  └──────┬───────┘
         │ HTTPS
  ┌──────▼───────────────────────────────────────┐
  │  FastAPI  (api/)                              │
  │  • JWT auth (Keycloak OIDC)                  │
  │  • HIPAA audit log on every PHI route        │
  │  • Rate limiter (SlowAPI)                     │
  │  • 12 route modules                           │
  └──┬───────────────────────────────────────────┘
     │ enqueues
  ┌──▼──────────────────────────────────────────┐
  │  Celery Workers                              │
  │  genomic_worker → ai_worker → notify_worker  │
  └──┬──────────────────────────────────────────┘
     │
  ┌──▼──────────────────────────────────────────┐
  │  AI / Evidence layer                         │
  │  AlphaMissense · OncoKB · OpenTargets        │
  │  DiffDock · AlphaFold · ChEMBL · CIViC       │
  └──┬──────────────────────────────────────────┘
     │ persists
  ┌──▼──────────────────────────────────────────┐
  │  PostgreSQL 16  (12 tables)                  │
  │  Redis  (task queue + rate limit cache)      │
  │  MinIO  (encrypted VCF/BAM storage)          │
  └─────────────────────────────────────────────┘
```

---

## Component catalogue

### Frontend — `web/`

| File / dir | Purpose |
|-----------|---------|
| `app/` | Next.js 14 App Router pages |
| `app/results/[id]/page.tsx` | Main results view — ranked drugs, evidence, repurposing |
| `app/explore/page.tsx` | Explore known variants and drugs |
| `components/CombinationTable.tsx` | Combination therapy display |
| `components/ImmunoPanel.tsx` | Immunotherapy biomarker panel |
| `components/SignatureCard.tsx` | Mutational signature visualization |
| `lib/api.ts` | Typed API client |

### Backend API — `api/`

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI app factory, CORS, lifespan hooks |
| `routes/submit.py` | Sample submission endpoint |
| `routes/results.py` | Fetch ranked drug results |
| `routes/repurposing.py` | Repurposing, trial matches, immunotherapy, combinations |
| `routes/marketplace.py` | Pharma marketplace bids |
| `routes/crowdfund.py` | Crowdfunding module |
| `routes/gdpr.py` | GDPR Art.17 erasure + Art.20 export |
| `routes/fhir.py` | HL7 FHIR R4 export |
| `middleware/rate_limit.py` | SlowAPI rate limiting |
| `middleware/logging_config.py` | Structured JSON logging |

### AI / Ranking — `api/ai/`

| File | Purpose |
|------|---------|
| `ranking.py` | Core ranking engine — composite weighted score |
| `ranking_config.py` | All tunable weights and thresholds (no magic numbers in logic) |

### Services — `api/services/`

| File | Purpose |
|------|---------|
| `oncokb_evidence.py` | Evidence table (294 entries · 74 genes) — the drug→level lookup |
| `benchmark.py` | Hard clinical benchmark — 81 cases, P@3 gate |
| `combination_therapy.py` | FDA-approved combination regimen detection |
| `immunotherapy_biomarkers.py` | TMB/MSI/HRD biomarker scoring |
| `mutational_signatures.py` | COSMIC v3 mutational signature analysis |
| `trial_integration.py` | ClinicalTrials.gov live matching |
| `oncologist_report.py` | Structured oncologist-facing report generation |

### Workers — `api/workers/`

| Worker | What it does |
|--------|-------------|
| `genomic_worker.py` | Runs Nextflow pipeline (GATK, BWA-MEM2, OpenCRAVAT) |
| `ai_worker.py` | Runs AlphaMissense + DiffDock + OncoKB + ranking |
| `custom_drug_worker.py` | Generates discovery brief (ChEMBL leads, AlphaFold, Ro5) |
| `notify_worker.py` | Sends email via Resend |
| `gdpr_worker.py` | Cascades GDPR erasure across all tables + MinIO |

### Genomics pipeline — `pipeline/`

Built with Nextflow. Modules:
- `fastqc` — quality control
- `trimmomatic` — adapter trimming
- `bwa_mem2` — alignment to GRCh38
- `gatk_haplotypecaller` — germline variant calling
- `opencravat` — variant annotation (ClinVar, COSMIC, gnomAD)

---

## Data flow: from VCF to ranked drugs

```
1.  Patient uploads VCF
        │
2.  genomic_worker annotates variants
        │  (OpenCRAVAT → ClinVar, COSMIC, gnomAD scores)
        │
3.  ai_worker scores each variant
        │  AlphaMissense: is this amino acid change pathogenic?
        │
4.  For each actionable variant:
        │
        ├─ Query oncokb_evidence._LEVEL_TABLE
        │   → returns per-drug OncoKB levels
        │
        ├─ Query OpenTargets GraphQL
        │   → target-disease association scores
        │
        ├─ (optional) DiffDock binding score
        │   → if AlphaFold structure available
        │
        ├─ Query ChEMBL for repurposing candidates
        │
        └─ rank_candidates() composite score
              DiffDock 25% + OpenTargets 20% + OncoKB 25%
              + AlphaMissense 10% + Phase 10% + CIViC 10%
              → resistance gate applied
              → source diversity penalty applied
              → drug_tier classification applied
              │
5.  Top-3 drugs returned per variant
        │  with evidence_audit_trail (per-source breakdown)
        │
6.  Combination therapy check (combination_therapy.py)
        │
7.  Immunotherapy biomarker check (TMB, MSI, HRD)
        │
8.  Mutational signature analysis
        │
9.  Result persisted to PostgreSQL
        │
10. notify_worker sends email to patient + oncologist
```

---

## Evidence table: how oncokb_evidence.py works

The core evidence lookup lives in `_LEVEL_TABLE` — a Python dict keyed by
`(gene_upper, normalised_alteration)` → `{drug_name: oncokb_level}`.

Key normalisation rules (see `_normalise_alteration()`):
- Strip `p.` prefix
- Uppercase amino acid 3-letter codes → 1-letter (e.g. `Val` → `V`)
- Strip separators (hyphens, spaces, dots) for compound lookups
- Check `_ALTERATION_ALIASES` for known synonyms (e.g. `etv6ntrk3` → `etv6-ntrk3`)

Cancer-type context overrides (`_CANCER_CONTEXT_OVERRIDES`) adjust levels
where the same mutation has different evidence depending on tumour type
(e.g. BRAF V600E has different approved drugs in melanoma vs CRC vs NSCLC).

Fallback chain for unrecognised variants:
1. Direct key lookup `(gene, alt_norm)`
2. Fuzzy substring match against all gene entries
3. Gene-level fallback (if AlphaMissense score ≥ threshold + gene has L1/L2)
4. Returns `{}` (no candidates) → system escalates to Tier 2/3

---

## Database schema (12 tables)

| Table | Description |
|-------|-------------|
| `patients` | Patient identity (keycloak_id, anonymised) |
| `submissions` | Raw submission (VCF filename, cancer type, VAF, purity) |
| `results` | Ranked drug output (JSON blob + structured fields) |
| `repurposing_candidates` | Per-drug repurposing scores |
| `oncologist_reviews` | Oncologist-submitted review scores |
| `drug_requests` | Custom drug discovery requests |
| `marketplace_bids` | Pharma manufacturer bids |
| `crowdfund_campaigns` | Patient crowdfunding campaigns |
| `cohorts` | Research cohort aggregations |
| `audit_log` | HIPAA PHI access log |
| `alembic_version` | Migration tracking |

---

## Security architecture

- **Auth:** Keycloak OIDC/OAuth2; JWT RS256 verified on every route
- **PHI:** All patient data encrypted at rest (AES-256 MinIO); TLS in transit
- **Audit:** Every PHI access written to `audit_log` with timestamp + user
- **Rate limiting:** SlowAPI on all routes (configurable per tier)
- **CI security:** Weekly pip-audit, npm audit, Bandit, Semgrep OWASP, Trivy
- **HIPAA:** §164.308 (admin) · §164.310 (physical) · §164.312 (technical)
- **GDPR:** Art. 17 cascade erasure + Art. 20 structured export

---

## Adding a new cancer type or evidence entry

1. **Evidence entry** — add to `_LEVEL_TABLE` in `api/services/oncokb_evidence.py`
2. **Cancer context** — add to `_CANCER_CONTEXT_OVERRIDES` for tumour-type-specific levels
3. **Benchmark case** — add a case to `HARD_CLINICAL_CASES` in `api/services/benchmark.py`
4. **Run gate** — `python scripts/hard_benchmark_gate.py` must still PASS
5. **PR** — include the gate output in your PR description

See [DRUG_DECISION_LOGIC.md](DRUG_DECISION_LOGIC.md) for the three-tier
decision framework and [CONTRIBUTING.md](../CONTRIBUTING.md) for the full
contributor workflow.
