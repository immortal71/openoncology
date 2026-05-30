# OpenOncology — Setup Guide

Clone, run, and verify the full stack in under 10 minutes.

---

## Prerequisites

| Tool | Version | Required for |
|------|---------|-------------|
| Python | ≥ 3.11 | Backend API |
| Node.js | ≥ 20 | Frontend |
| Docker + Compose | any recent | Full-stack one-command start |
| Git | any | Cloning |

---

## Option A — Docker (recommended, 3 commands)

```bash
git clone https://github.com/immortal71/openoncology.git
cd openoncology
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

That's it. All services (Postgres, Redis, MinIO, Keycloak) start automatically.

---

## Option B — Local development (backend + frontend separately)

### 1. Clone the repo

```bash
git clone https://github.com/immortal71/openoncology.git
cd openoncology
```

### 2. Backend

```bash
# Create virtual environment
python -m venv .venv

# Activate
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\Activate.ps1       # Windows PowerShell

# Install dependencies
cd api
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env             # edit as needed (see below)

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API is now live at http://localhost:8000 — visit /docs for the interactive Swagger UI.

### 3. Frontend

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Frontend is now live at http://localhost:3000.

---

## Environment variables

Create `api/.env` (or export these in your shell):

```dotenv
# ── Database ──────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./dev.db           # SQLite for local dev
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/openoncology

# ── Redis (required for Celery workers) ───────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Auth ──────────────────────────────────────────────────────────
SECRET_KEY=change-me-in-production-min-32-chars
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=openoncology
KEYCLOAK_CLIENT_ID=openoncology-api

# ── Optional — improves drug evidence quality ─────────────────────
ONCOKB_API_TOKEN=                         # free token at oncokb.org/account/register
OPENAI_API_KEY=                           # enables GPT-4o plain-English summaries

# ── Optional — storage ────────────────────────────────────────────
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=openoncology-raw

# ── Optional — payments ───────────────────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

> Without `ONCOKB_API_TOKEN` the system falls back to a curated 294-entry
> static table (74 actionable genes). All benchmark and demo functionality
> works without any API keys.

---

## Verify the installation

### Run the test suite

```bash
cd api
python -m pytest tests/ -q
```

Expected: all tests pass.

### Run the benchmark gate

```bash
cd ..
python scripts/hard_benchmark_gate.py
```

Expected output ends with:
```
Gate result: PASS
Standard P@3: 0.817   Hit@3: 100.0%   FP: 0
```

### Quick smoke test

```bash
python -c "
import sys, asyncio
sys.path.insert(0,'api'); sys.path.insert(0,'.')
from services.oncokb_evidence import get_all_drugs_for_variant_live
result = get_all_drugs_for_variant_live('EGFR', 'L858R', 'Non-Small Cell Lung Cancer')
print('Evidence test:', result)
assert 'osimertinib' in result, 'Evidence table not loading correctly'
print('OK')
"
```

---

## Running with the sample VCF files

Three sample VCF files are in `samples/`:

```bash
# EGFR L858R — should recommend osimertinib as top drug
samples/egfr_t790m_demo.vcf

# NSCLC panel
samples/demo_output_sample3_nsclc.json

# Real patient DNA (anonymized)
samples/real/
```

To run the API pipeline against a sample:

```bash
# Start the API first, then:
curl -X POST http://localhost:8000/api/submit \
  -F "vcf_file=@samples/sample_dna.vcf" \
  -F "cancer_type=Non-Small Cell Lung Cancer" \
  -H "Authorization: Bearer <token>"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: services` | Run from repo root with `sys.path.insert(0,'api')` or `cd api` first |
| `401 Unauthorized` from OncoKB | Expected without token — system uses static fallback, no action needed |
| `alembic upgrade head` fails | Delete `api/dev.db` and retry, or check `DATABASE_URL` |
| Port 8000 already in use | `uvicorn main:app --reload --port 8001` |
| Redis connection refused | Start Redis locally: `docker run -p 6379:6379 redis:alpine` |
| `npm run dev` fails | Ensure Node ≥ 20: `node --version`; run `npm install` first |
| Docker build slow | Add `--no-cache` only if a dependency changed; first build downloads ~2GB |

---

## Project structure (quick map)

```
openoncology/
├── api/                    # FastAPI backend (Python)
│   ├── ai/                 # Ranking algorithm + config
│   ├── models/             # SQLAlchemy ORM models
│   ├── routes/             # HTTP route handlers (12 modules)
│   ├── services/           # Business logic, evidence table, benchmark
│   ├── workers/            # Celery async workers
│   └── tests/              # pytest test suite
├── web/                    # Next.js 14 frontend (TypeScript)
├── pipeline/               # Nextflow genomics pipeline
├── scripts/                # Benchmark, validation, analysis scripts
├── docs/                   # All documentation (you are here)
├── infra/                  # Kubernetes + Helm + Prometheus
└── docker-compose.yml      # One-command full-stack
```

For a deeper explanation of every component see [ARCHITECTURE.md](ARCHITECTURE.md).
