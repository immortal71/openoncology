# OpenOncology — Build Log

> Last updated: March 19, 2026
> Phase: **3 — AI Drug Repurposing** ✅ COMPLETE

---

## ✅ PHASE 1 — COMPLETE (What's Been Built)

### Infrastructure
| File | Status | Notes |
|---|---|---|
| `docker-compose.yml` | ✅ Done | All 10 services: web, api, 3 workers, db, redis, minio, keycloak, prometheus, grafana |
| `.env.example` | ✅ Done | All secrets template — copy to `.env` and fill values |

### Backend — FastAPI (`api/`)
| File | Status | Notes |
|---|---|---|
| `api/main.py` | ✅ Done | App entrypoint, CORS, lifespan, route registration |
| `api/config.py` | ✅ Done | Pydantic settings from env vars |
| `api/database.py` | ✅ Done | Async SQLAlchemy engine + session |
| `api/Dockerfile` | ✅ Done | Python 3.11 slim image |
| `api/requirements.txt` | ✅ Done | All dependencies pinned |
| `api/routes/auth.py` | ✅ Done | Keycloak JWT validation, `/api/auth/me` |
| `api/routes/submit.py` | ✅ Done | File upload, encryption, Celery job dispatch |
| `api/routes/results.py` | ✅ Done | Mutation results + patient dashboard |
| `api/routes/repurposing.py` | ✅ Done | Drug repurposing candidates per result |
| `api/routes/marketplace.py` | ✅ Done | Pharma listing + Stripe order creation |
| `api/routes/crowdfund.py` | ✅ Done | Campaign create, public view, Stripe donation |

### Database Models (`api/models/`)
| Model | Table | Status |
|---|---|---|
| `Patient` | `patients` | ✅ Done |
| `Submission` | `submissions` | ✅ Done |
| `Mutation` | `mutations` | ✅ Done |
| `Result` | `results` | ✅ Done |
| `RepurposingCandidate` | `repurposing` | ✅ Done |
| `Campaign` | `campaigns` | ✅ Done |
| `Order` | `orders` | ✅ Done |
| `PharmaCompany` | `pharma_companies` | ✅ Done |
| `Oncologist` | `oncologists` | ✅ Done |

### Workers (`api/workers/`)
| Worker | Status | Notes |
|---|---|---|
| `genomic_worker.py` | ✅ Done | Downloads DNA, runs Nextflow pipeline, parses VCF, stores mutations |
| `ai_worker.py` | ✅ Done | AlphaMissense + OncoKB + OpenTargets + DiffDock (stubs for Phase 3) |
| `notify_worker.py` | ✅ Done | Resend email on results ready |
| `_db_sync.py` | ✅ Done | Sync DB session for Celery workers |

### Frontend — Next.js (`web/`)
| File | Status | Notes |
|---|---|---|
| `web/package.json` | ✅ Done | All deps including Stripe, Radix, Framer Motion |
| `web/tsconfig.json` | ✅ Done | Strict TypeScript config |
| `web/next.config.js` | ✅ Done | Env vars, image config |
| `web/app/layout.tsx` | ✅ Done | Root layout with React Query + Toaster |
| `web/app/globals.css` | ✅ Done | Tailwind base styles + CSS variables |
| `web/app/page.tsx` | ✅ Done | Landing page — hero, features, steps |
| `web/app/submit/page.tsx` | ✅ Done | File upload form with validation |
| `web/app/results/[id]/page.tsx` | ✅ Done | Results page — mutations table, status polling |
| `web/lib/api.ts` | ✅ Done | Typed API client |
| `web/components/providers/QueryProvider.tsx` | ✅ Done | React Query provider |
| `web/components/ui/toaster.tsx` | ✅ Done | Radix toast |
| `web/Dockerfile` | ✅ Done | Multi-stage Docker build |

### Bioinformatics Pipeline — Nextflow (`pipeline/`)
| File | Status | Notes |
|---|---|---|
| `pipeline/main.nf` | ✅ Done | Full workflow: FastQC → Trimmomatic → BWA-MEM2 → GATK → OpenCRAVAT |
| `pipeline/modules/fastqc.nf` | ✅ Done | Quality control |
| `pipeline/modules/trimmomatic.nf` | ✅ Done | Adapter trimming |
| `pipeline/modules/bwa_mem2.nf` | ✅ Done | Alignment to GRCh38 |
| `pipeline/modules/gatk.nf` | ✅ Done | Variant calling + filtering |
| `pipeline/modules/opencravat.nf` | ✅ Done | ClinVar, COSMIC, OncoKB annotation |
| `pipeline/conf/local.config` | ✅ Done | Local development config |

---

## ✅ PHASE 2 — COMPLETE (Months 3–4)
**Goal: Real mutation detection from a VCF file, results shown on the frontend**

### Backend
- [x] `api/services/oncokb.py` — OncoKB REST API client (Bearer token, annotate by protein change)
- [x] `api/services/clinvar.py` — ClinVar E-utilities client (esearch + efetch, clinical significance)
- [x] `api/services/civic.py` — CIViC GraphQL client (variant evidence query)
- [x] `api/routes/oncologist.py` — Oncologist review portal (`/pending`, `/review`)
- [x] `api/routes/webhook.py` — Stripe webhook (`payment_intent.succeeded` → Order/Campaign update)
- [x] `api/alembic/env.py` + `api/alembic.ini` — Alembic async migrations setup
- [x] `api/alembic/versions/0001_initial_schema.py` — Full first migration (all 9 tables + indexes)
- [x] `api/main.py` — Registered oncologist + webhook routers

### Pipeline
- [x] `pipeline/scripts/download_references.sh` — GRCh38 + BWA-MEM2 index + dbSNP 151 download

### Frontend
- [x] `web/app/repurposing/[id]/page.tsx` — Drug candidates with score bars, ChEMBL links
- [x] `web/app/marketplace/page.tsx` — Pharma grid + Stripe PaymentIntent order form
- [x] `web/app/dashboard/page.tsx` — Patient dashboard, status badges, auto-refresh
- [x] `web/app/crowdfund/[id]/page.tsx` — Public campaign page + Stripe Elements donation form
- [x] `web/app/oncologist/page.tsx` — Oncologist review portal (approve/flag with notes)
- [x] `web/lib/auth.ts` — Keycloak JS adapter (silent SSO, token refresh, role parsing)
- [x] `web/middleware.ts` — Next.js Edge middleware (protects /dashboard, /submit, /oncologist)
- [x] `web/components/providers/AuthProvider.tsx` — React context, sets kc_auth/kc_role cookies
- [x] `web/public/silent-check-sso.html` — Keycloak silent SSO page
- [x] `web/app/layout.tsx` — Wrapped with AuthProvider

### DevOps
- [x] `infra/prometheus.yml` — Prometheus scrape config (API + DB + Redis + workers)
- [x] `.github/workflows/ci.yml` — CI: ESLint+tsc, Ruff, pytest, Docker build check

---

## ✅ PHASE 3 — COMPLETE — AI Drug Repurposing (Months 5–6)

### AlphaMissense Integration
- [x] `ai/alphamissense/classify.py` — SQLite-backed classifier; `score()`, `classify()`, `score_and_classify()`; graceful fallback when DB absent
- [x] `ai/alphamissense/download_scores.py` — Downloads AlphaMissense_hg38.tsv.gz from Zenodo (~3.6 GB) and imports into `scores.db` SQLite with indexed lookup
- [x] `ai/__init__.py`, `ai/alphamissense/__init__.py` — Python packages

### DiffDock Integration
- [x] `ai/diffdock/prepare_inputs.py` — Fetches AlphaFold PDB via EBI API + converts SMILES → SDF via RDKit
- [x] `ai/diffdock/score.py` — DiffDock subprocess wrapper; parses `rank1_confidence*.sdf` filename; normalises to [0,1] via sigmoid; returns None gracefully when DiffDock not installed
- [x] `ai/diffdock/__init__.py`

### OpenTargets Full GraphQL Integration
- [x] `api/services/opentargets.py` — Three queries: `get_target_id()` (gene→ENSG), `get_drugs_for_target()` (drugs with MOA/phase/disease/score), `get_evidence_scores()` (disease association breakdown)

### ChEMBL REST API Integration
- [x] `api/services/chembl.py` — `get_molecule()` (SMILES, MW, Ro5, approval), `search_molecule_by_name()`, `get_mechanisms_for_target()`, `get_activities_for_target()` (IC50/Ki/Kd)

### Drug Ranking Algorithm
- [x] `api/ai/ranking.py` — `compute_rank_score()` with weighted combination: DiffDock 30% + OpenTargets 25% + OncoKB 25% + AlphaMissense 10% + Clinical phase 10%; missing components handled by weight redistribution
- [x] `api/ai/__init__.py`

### AI Worker — Stubs → Real Implementations
- [x] `_run_alphamissense()` — now uses `AlphaMissenseClassifier` with HGVS→short form conversion + gene→UniProt mapping (30 key oncogenes)
- [x] `_query_opentargets()` — now uses full OpenTargets + ChEMBL enrichment + DiffDock scoring pipeline
- [x] Ranking now uses `rank_candidates()` from `api/ai/ranking.py`

### Dependencies
- [x] `api/requirements.txt` — added `rdkit==2024.3.2` (SMILES→SDF), `ruff==0.4.4` (linter)

---

## ✅ PHASE 4 — Marketplace & Crowdfunding (Months 7–9)

**Completed files:**

| File | Description |
|---|---|
| `api/routes/pharma_admin.py` | Pharma company apply/list/verify admin endpoints |
| `api/routes/stripe_connect.py` | Stripe Connect Express onboarding, status, payout |
| `api/routes/campaign.py` | Full crowdfund lifecycle: create/activate/donate/close/complete + milestone hooks |
| `api/services/email_templates.py` | 5 HTML email templates (results, milestone, order, pharma approved, review) |
| `api/workers/notify_worker.py` | 5 Celery notify tasks wired to Resend + Keycloak email lookup |
| `web/app/admin/pharma/page.tsx` | Admin UI: review applications, approve/reject, Stripe Connect onboard |
| `web/app/dashboard/campaigns/page.tsx` | Patient UI: create, publish, share, close campaigns + progress bar |

**Key integrations:**
- Stripe Connect Express: KYC onboarding → `POST /api/stripe/connect/onboard/{id}` returns AccountLink URL
- Stripe Transfer: campaign completion triggers server-side `Transfer` to pharma Express account
- Campaign milestones at 25 / 50 / 75 / 100 % automatically dispatch `notify_campaign_milestone` Celery task
- All 3 new routers registered in `api/main.py`
- Email rendered from shared `_layout()` wrapper with inline CSS (no external stylesheet dependency)

---

## ✅ PHASE 5 — Public Launch (Months 10–12)

**Completed files:**

| File | Description |
|---|---|
| `infra/helm/Chart.yaml` | Helm chart definition (depends on Bitnami postgresql + redis sub-charts) |
| `infra/helm/values.yaml` | Base Helm values (replicas, images, ingress, HPA config) |
| `infra/helm/values.production.yaml` | Production overrides (higher replicas, HSTS headers, pull-always) |
| `infra/helm/templates/_helpers.tpl` | Shared label/name helpers + DB/Redis URL templates |
| `infra/helm/templates/configmap.yaml` | All non-secret env vars (URLs, bucket names, realm) |
| `infra/helm/templates/api.yaml` | API Deployment + ClusterIP Service + HorizontalPodAutoscaler |
| `infra/helm/templates/web.yaml` | Next.js Deployment + ClusterIP Service |
| `infra/helm/templates/workers.yaml` | Range loop — genomic/ai/notify Celery worker Deployments |
| `infra/helm/templates/ingress.yaml` | NGINX Ingress with cert-manager TLS for web/api/keycloak |
| `infra/helm/templates/postgres.yaml` | PostgreSQL StatefulSet + PVC + Service |
| `infra/helm/templates/keycloak.yaml` | Keycloak Deployment (KC_PROXY=edge) + Service |
| `infra/helm/templates/serviceaccount.yaml` | Least-privilege ServiceAccount |
| `infra/k8s/namespace.yaml` | Namespace (Pod Security Standards: restricted) + RBAC + NetworkPolicy (deny-all, allow-necessary) |
| `api/routes/gdpr.py` | `GET /api/me/export` (Art. 20 JSON export) + `DELETE /api/me` (Art. 17 erasure) |
| `api/workers/gdpr_worker.py` | Celery task: cascade DB delete → MinIO cleanup → Keycloak user delete → confirmation email |
| `api/models/deletion_request.py` | DeletionRequest model (audit trail for erasure requests) |
| `api/middleware/audit.py` | HIPAA `AuditMiddleware` — structured PHI access log (user, path, IP, duration) |
| `api/middleware/rate_limit.py` | SlowAPI limiter (Redis-backed; 120 req/min default; strict limits for auth/upload) |
| `api/middleware/__init__.py` | Package marker |
| `.github/workflows/security.yml` | Weekly security CI: pip-audit, npm audit, Bandit SAST, Semgrep OWASP, ZAP baseline, Trivy container scan |
| `infra/zap/rules.tsv` | ZAP alert filter rules (FAIL on path-traversal, SSRF, RCE; WARN on CSP/XSS) |
| `docs/HIPAA_COMPLIANCE.md` | Full HIPAA §164.308/310/312 checklist + GDPR overlap + incident response table |

**Key security controls implemented:**
- Network Policies: default deny-all with explicit allow-lists per service
- Pod Security Standards: `restricted` namespace profile (non-root, read-only FS, drop ALL caps)
- RBAC: ServiceAccount with minimal `get/list/watch` ConfigMap/Secret access only
- HIPAA Audit Logging: every PHI endpoint logs who/what/when/where — never logs PHI values
- Rate limiting: 10 req/min on auth, 5 req/min on uploads, 120 req/min global
- GDPR: full erasure (DB cascade + MinIO + Keycloak) + JSON export endpoints
- Automated security scanning on every push to main + weekly schedule

**Deploy command:**
```bash
# Apply namespace + RBAC + network policies first
kubectl apply -f infra/k8s/namespace.yaml

# Install/upgrade Helm chart
helm upgrade --install openoncology ./infra/helm \
  -f infra/helm/values.yaml \
  -f infra/helm/values.production.yaml \
  --namespace openoncology \
  --create-namespace
```

---

## How to Start Right Now

```bash
# 1. Copy and fill environment variables
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Install frontend dependencies
cd web && npm install && cd ..

# 4. Run frontend in dev mode
cd web && npm run dev

# 5. API docs available at
#    http://localhost:8000/docs
```

---

## Service URLs (local)
| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Keycloak | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
