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

# 3. Start all 10 services
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
| `OPENAI_API_KEY` | Optional | Enables GPT-4o plain-language summaries. Falls back to template if unset |
| `STRIPE_SECRET_KEY` | Optional | Required only for marketplace/crowdfunding payments |
| `STRIPE_WEBHOOK_SECRET` | Optional | Required for Stripe webhook verification |
| `RESEND_API_KEY` | Optional | Email notifications via Resend |
| `COSMIC_EMAIL` / `COSMIC_PASSWORD` | Optional | COSMIC v3.1 download credentials |

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
| **OncoKB token** | Without a token the pipeline uses a curated static table (294 entries, 74 actionable genes). A free academic token expands Tier 1 coverage significantly. |
| **AlphaMissense DB** | The 3.6 GB SQLite database is downloaded on first use. Ensure you have enough disk space and allow a few minutes on first startup. |
| **AlphaFold Server** | Protein structures are fetched from the AlphaFold Server API — no local GPU required. |
| **OpenAI key** | If `OPENAI_API_KEY` is not set, GPT-4o summaries fall back to a deterministic template. Core drug ranking is unaffected. |
| **Stripe** | Marketplace and crowdfunding features require a Stripe account with Connect Express enabled. These features are gracefully disabled if `STRIPE_SECRET_KEY` is unset. |

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|:--------|:-------------|:----|
| API returns 500 on first request | Tables not created | Run `alembic upgrade head` or set `ENVIRONMENT=development` |
| `Connection refused` to PostgreSQL | Container not ready | Wait 10–15 s and retry; add `pg_isready` health check |
| Frontend shows blank page | `NEXT_PUBLIC_API_URL` wrong | Set it to `http://localhost:8000` in `.env.local` |
| Keycloak redirect loop | Realm not configured | Access http://localhost:8080, import `infra/keycloak/realm.json` |
| MinIO bucket error | Bucket not created | Start MinIO, create `openoncology-raw`, `openoncology-vcf`, `openoncology-reports` buckets |
| Worker not processing tasks | Redis unreachable | Verify `REDIS_URL` and that Redis container is running |
| AlphaMissense slow first run | DB download | Expected — 3.6 GB download. Subsequent runs use cached DB |

---

*Back to [README.md](README.md) · [docs/METHODS.md](docs/METHODS.md) · [CONTRIBUTING.md](CONTRIBUTING.md)*
