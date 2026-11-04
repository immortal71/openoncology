# Deploying the public demo to Vercel

This covers the fastest, safest way to put OpenOncology in front of people at
**oncopurpose.com**: a frontend-only deployment of `web/` on Vercel, running in
demo mode. It needs no database, no Redis, no MinIO, no Keycloak, and touches
no real patient data. The demo flow (`?demo=true`) serves the canned KRAS
G12C case entirely from `web/lib/demo-data.ts`, with no calls to the backend
API. This is deliberately separate from `docs/RUNBOOK_STAGING_DEPLOY.md`,
which stands up the full stack (Postgres, MinIO, Keycloak, Celery workers) on
Kubernetes and is not yet production-ready; see that doc's own warning that
nothing in the chart has been applied to a cluster yet.

## What this gives you

- The marketing homepage and the full `/results/demo-nsclc-kras-g12c?demo=true`
  walkthrough, live at oncopurpose.com.
- Automatic redeploys on every push to `main` (once connected).
- No secrets to manage, no server to run.

## What this does NOT give you

- Real submissions (`/submit`, `/workspace`) won't work end-to-end. They
  call the FastAPI backend, which isn't deployed here. Phase 2, below,
  covers that.
- No auth, no database, no audit logging. Correct for a demo, not for
  anything handling real patient data.

## Steps

### 1. Connect the repo (one-time, needs your GitHub login)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
   (`immortal71`).
2. **Add New... → Project**, import `immortal71/openoncology`.
3. On the configure screen:
   - **Root Directory**: `web` (click Edit next to it: this is the one
     setting that matters; Vercel auto-detects Next.js once it's set).
   - Framework Preset: Next.js (auto-detected).
   - Build/output settings: leave as default.
   - Environment variables: none required. Leave `NEXT_PUBLIC_API_URL`
     unset; demo mode never reads it.
4. Click **Deploy**. First build takes a couple of minutes, then you'll get a
   `*.vercel.app` URL to sanity-check before the custom domain is attached.

### 2. Point oncopurpose.com at it

1. In the Vercel project, **Settings → Domains → Add**, enter
   `oncopurpose.com` (and `www.oncopurpose.com` if you want both).
2. Vercel will show the exact DNS records to add, typically an `A` record
   on the apex (`@`) to `76.76.21.21`, and a `CNAME` on `www` to
   `cname.vercel-dns.com`. Use whatever Vercel's UI actually displays; it
   occasionally changes.
3. In Bizee's domain management for oncopurpose.com (the page you
   screenshotted: look for a "DNS" or "Manage DNS" tab there, separate from
   the renewal/privacy page), add those records.
4. DNS propagation is usually minutes, sometimes a few hours. Vercel's
   Domains tab shows a live "Valid Configuration" check once it resolves.

### 3. Point the GitHub repo at the live site

Once the domain resolves, update the repo's **About → Website** field to
`https://oncopurpose.com` (Settings aren't needed; it's the pencil icon next
to About on the repo's main page), so the link shows up next to the repo
description.

## Phase 2 (not done, future work): a real backend

`web/submit` and `web/workspace` need the FastAPI backend, Postgres, Redis,
and (for custom-drug jobs) Celery plus MinIO. Two realistic paths once you're
ready for that:

- **Follow `docs/RUNBOOK_STAGING_DEPLOY.md`** as-is. It's the existing,
  more complete path (Keycloak auth, HIPAA-oriented controls, Helm chart),
  but needs a Kubernetes cluster and has never been run end-to-end yet.
- **Render**, as a lighter-weight alternative to Kubernetes for a first real
  backend: a web service for `api/`, a background worker for the Celery
  tasks, Render's managed Postgres and Redis, and an S3-compatible bucket
  in place of self-hosted MinIO (Render has no native MinIO equivalent;
  Cloudflare R2 or Backblaze B2 work as drop-in S3 alternatives). This isn't
  built yet; ask and it can be scaffolded (`render.yaml` blueprint) the same
  way this doc scaffolded the Vercel path.

Either path should keep `docs/ROADMAP_TO_CLINICAL_USE.md`'s rule: no real
patient data until that roadmap says so.
