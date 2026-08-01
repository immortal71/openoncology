# OpenOncology — Setup Guide

Everything you need to run OpenOncology locally, in Docker, or on Kubernetes.

---

## 1. Prerequisites

| Tool | Minimum version | Notes |
|:-----|:----------------|:------|
| **Docker** + Docker Compose | 24 / v2 | Option A (recommended) |
| **Python** | 3.11+ | Option B — backend only |
| **Node.js** | 18 LTS | Option B — frontend only |
| **PostgreSQL** | 15+ | Option B — or use Docker service |
| **Redis** | 7+ | Option B — or use Docker service |
| **MinIO** | Latest | Option B — or use Docker service |

---

## 2. Option A — Docker (3 minutes)

```bash
# 1. Clone
git clone https://github.com/immortal71/openoncology.git
cd openoncology

# 2. Copy the env template and fill in your secrets (see §4)
cp .env.example .env

# 3. Start all services
docker compose up -d

# 4. Wait ~30 seconds for services to initialize, then open:
open http://localhost:3000   # macOS
start http://localhost:3000  # Windows
xdg-open http://localhost:3000  # Linux
```

### Service URLs after `docker compose up -d`

| Service | URL | Default credentials |
|:--------|:----|:--------------------|
| 🌐 Patient web app | http://localhost:3000 | Register via Keycloak |
| 📖 FastAPI interactive docs | http://localhost:8000/docs | — |
| 🔑 Keycloak admin | http://localhost:8080 | `admin` / `KEYCLOAK_ADMIN_PASSWORD` from `.env` |
| 🗄️ MinIO console | http://localhost:9001 | `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` from `.env` |
| 📊 Prometheus metrics | http://localhost:9090 | — |
| 📈 Grafana dashboards | http://localhost:3001 | `admin` / `GRAFANA_PASSWORD` from `.env` |

> **First run:** The API auto-creates all database tables in development mode (`bootstrap_schema_in_dev=True`). For migration-managed environments run `alembic upgrade head` first.

---

## 3. Option B — Local Development

### Backend

```bash
cd api
python -m venv .venv
# Activate:
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env             # edit DATABASE_URL + REDIS_URL to point at your local services
alembic upgrade head             # apply migrations
uvicorn main:app --reload        # API at http://localhost:8000
```

Workers (each in a separate terminal):

```bash
cd api
celery -A workers.genomic_worker worker --loglevel=info -Q genomic
celery -A workers.ai_worker worker --loglevel=info -Q ai
celery -A workers.notify_worker worker --loglevel=info -Q notify
```

### Frontend

```bash
cd web
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                         # web at http://localhost:3000
```

---

## 4. Environment Variables

Copy `.env.example` to `.env` (root) and fill in the values below.

| Variable | Required | Description |
|:---------|:---------|:------------|
| `DB_PASSWORD` | ✅ | PostgreSQL password for `openoncology` user |
| `SECRET_KEY` | ✅ | 32+ random characters for JWT signing — never commit this |
| `MINIO_ACCESS_KEY` | ✅ | MinIO root access key |
| `MINIO_SECRET_KEY` | ✅ | MinIO root secret |
| `KEYCLOAK_ADMIN_PASSWORD` | ✅ | Keycloak admin console password |
| `GRAFANA_PASSWORD` | ✅ | Grafana admin password |
| `ONCOKB_API_TOKEN` | Recommended | Free academic token — improves Tier 1 drug coverage. Register at https://oncokb.org/account/register |
| `ALPHAFOLD_API_KEY` | Optional | Bearer token for AlphaFold Server API calls (structure generation works unauthenticated too, subject to rate limits — see §6) |
| `OPENAI_API_KEY` | Optional | Enables GPT-4o plain-language summaries. Falls back to template if unset |
| `STRIPE_SECRET_KEY` | Optional | Required only for marketplace/crowdfunding payments |
| `STRIPE_WEBHOOK_SECRET` | Optional | Required for Stripe webhook verification |
| `RESEND_API_KEY` | Optional | Email notifications via Resend |
| `COSMIC_EMAIL` / `COSMIC_PASSWORD` | Optional | COSMIC v3.1 download credentials |

There is no single `MINIO_BUCKET` variable — bucket names are fixed in `api/config.py` (`bucket_raw`, `bucket_vcf`, `bucket_reports`, defaulting to `openoncology-raw`/`-vcf`/`-reports`) and buckets are auto-created on first upload.

> **Security note:** Never commit `.env` to git. It is already in `.gitignore`. Generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`.

---

## 5. Production Kubernetes Deploy

```bash
# Add chart sub-dependencies (PostgreSQL, Redis via Bitnami)
helm dependency update infra/helm

# Deploy to your cluster
helm upgrade --install openoncology infra/helm \
  --namespace openoncology --create-namespace \
  -f infra/helm/values.production.yaml \
  --set secrets.postgresPassword="$DB_PASSWORD" \
  --set secrets.secretKey="$SECRET_KEY" \
  --set secrets.oncokbToken="$ONCOKB_API_TOKEN"
```

The production chart includes HorizontalPodAutoscaler, cert-manager TLS, NGINX ingress, Pod Security Standards (`restricted`), and deny-all NetworkPolicy with explicit allow-lists.

---

## 6. First Run Notes

| Topic | Detail |
|:------|:-------|
| **Database migrations** | Run `alembic upgrade head` in `api/` before starting the server in production. In `development` mode (`ENVIRONMENT=development`) tables are auto-created on startup. |
| **OncoKB token** | Without a token the pipeline uses a curated static table (335 entries). A free academic token expands Tier 1 coverage significantly. |
| **AlphaMissense DB** | The 3.6 GB SQLite database is downloaded on first use. Ensure you have enough disk space and allow a few minutes on first startup. |
| **AlphaFold structures** | High-pathogenicity variants trigger a live call to the AlphaFold Server prediction API (`https://alphafoldserver.com/api`) to generate a mutation-specific structure. This works unauthenticated but is subject to rate limiting; set `ALPHAFOLD_API_KEY` to raise the limit. No local GPU is needed for this step — AlphaFold Server does the folding remotely. |
| **DiffDock docking** | Binding-confidence scoring via DiffDock is a separate step from AlphaFold structure generation, and **does** require real GPU compute — it is not optional infrastructure, it changes the actual ranking score. Verified working end-to-end on a Vultr NVIDIA A16 GPU instance (driver 550.90.07, CUDA 12.4, PyTorch 1.13.1+cu117); wiring the pipeline to call that instance (vs. a local install) is in progress — see `ai/diffdock/score.py`'s `DIFFDOCK_DIR`/`DIFFDOCK_PYTHON` env vars. Until that wiring lands, `binding_score` is `None` for every case and DiffDock's weight (15%) is dropped from the ranking, not scored as zero. |
| **OpenAI key** | If `OPENAI_API_KEY` is not set, GPT-4o summaries fall back to a deterministic template. Core drug ranking is unaffected. |
| **Stripe** | Marketplace and crowdfunding features require a Stripe account with Connect Express enabled. These features are gracefully disabled if `STRIPE_SECRET_KEY` is unset. |

---

## 7. Verify the Installation

### Run the test suite

```bash
cd api
python -m pytest tests/ -q
```

Expected: all tests pass.

### Run the hard benchmark gate

```bash
python scripts/hard_benchmark_gate.py
```

Prints `PASS`/`FAIL` against the current Standard P@3 and Hit@3 thresholds defined in the script — see [docs/BENCHMARK.md](BENCHMARK.md) for the current reconciled metric values rather than a specific expected console line, which drifts as the validation dataset changes.

### Quick smoke test

```bash
python -c "
import sys
sys.path.insert(0,'api'); sys.path.insert(0,'.')
from services.oncokb_evidence import get_all_drugs_for_variant_live
result = get_all_drugs_for_variant_live('EGFR', 'L858R', 'Non-Small Cell Lung Cancer')
print('Evidence test:', result)
assert 'osimertinib' in result, 'Evidence table not loading correctly'
print('OK')
"
```

---

## 8. Running with the Sample Files

Sample VCF and biopsy files are in `samples/`, including `samples/egfr_t790m_demo.vcf` (a demo EGFR T790M + TP53 case with real ClinVar/COSMIC IDs) and `samples/real/` (anonymized real patient data).

To submit a sample through the running API (matches the actual `/api/submit/` route contract in `api/routes/submit.py` — trailing slash, `biopsy_file` + `dna_file` fields, not a single `vcf_file`):

```bash
curl -X POST http://localhost:8000/api/submit/ \
  -H "Authorization: Bearer <token>" \
  -F "biopsy_file=@samples/sample_biopsy.pdf;type=application/pdf" \
  -F "dna_file=@samples/egfr_t790m_demo.vcf;type=text/plain" \
  -F "cancer_type=NSCLC"
```

In `ENVIRONMENT=development`, the bearer token `demo-local-token` bypasses real Keycloak auth (see `routes/auth.py`) for local testing.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|:--------|:-------------|:----|
| API returns 500 on first request | Tables not created | Run `alembic upgrade head` or set `ENVIRONMENT=development` |
| `Connection refused` to PostgreSQL | Container not ready | Wait 10–15 s and retry; add `pg_isready` health check |
| Frontend shows blank page | `NEXT_PUBLIC_API_URL` wrong | Set it to `http://localhost:8000` in `.env.local` |
| Keycloak redirect loop | Realm not configured | Access http://localhost:8080, import `infra/keycloak/realm.json` |
| MinIO bucket error | Bucket not created | Buckets auto-create on first upload; if using MinIO standalone (not Docker), ensure server-side encryption/KMS is configured or uploads will 501 |
| Worker not processing tasks | Redis unreachable | Verify `REDIS_URL` and that Redis container is running |
| AlphaMissense slow first run | DB download | Expected — 3.6 GB download. Subsequent runs use cached DB |
| `401 Unauthorized` from OncoKB | Expected without token | System uses static fallback table, no action needed |
| `ModuleNotFoundError: services` (running scripts from repo root) | Python path | Run from `api/` directly, or `sys.path.insert(0, 'api')` before importing |

---

## 10. Project Structure (Quick Map)

```
openoncology/
├── api/                    # FastAPI backend (Python)
│   ├── ai/                 # Ranking algorithm + config
│   ├── models/             # SQLAlchemy ORM models
│   ├── routes/             # HTTP route handlers
│   ├── services/           # Business logic, evidence table, benchmark
│   ├── workers/            # Celery async workers
│   └── tests/              # pytest test suite
├── ai/                     # DiffDock, AlphaMissense, AlphaFold, repurposing modules
│   ├── diffdock/           # DiffDock binding-confidence scorer (requires GPU — see §6)
│   ├── alphamissense/      # Pathogenicity classifier
│   └── services/           # AlphaFold Server client, etc.
├── web/                    # Next.js frontend (TypeScript)
├── pipeline/               # Nextflow genomics pipeline
├── scripts/                # Benchmark, validation, analysis scripts
├── docs/                   # All documentation (you are here)
├── infra/                  # Kubernetes + Helm + Prometheus
└── docker-compose.yml      # One-command full-stack
```

For a deeper explanation of every component see [ARCHITECTURE.md](ARCHITECTURE.md).

---

*Back to [README.md](../README.md) · [docs/METHODS.md](METHODS.md) · [CONTRIBUTING.md](../CONTRIBUTING.md)*
