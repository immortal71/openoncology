# Runbook: first staging deploy

**Status.** Gates 1 and 3 are done. Images publish to GHCR on every push to
`main`, and `values.staging.yaml` names the environment honestly and pins an
immutable tag. What remains needs a cluster and secrets, which is what this
document is for.

**Read this first.** Nothing in the chart has ever run. Every manifest renders
and passes `kubeconform`, and not one has been applied to a cluster. MinIO has
never started, the backup CronJob has never dumped anything, the `kcadm` Job has
never authenticated, and no Prometheus has loaded the alert rules. Expect the
first install to find things. That is what it is for.

**This is research-use software.** `docs/ROADMAP_TO_CLINICAL_USE.md` is the
authority on what that means. Staging must not receive real patient data.

---

## Step 0: decide package visibility

The `publish-images` job pushes to GHCR, and packages default to **private**.

- **Private**, the safer default. The cluster needs an `imagePullSecret`, added
  in step 3.
- **Public**, simpler. Anyone can pull your API and web images. The images
  contain your application code; the repository is already public, so this
  mostly changes how easily someone runs it, not what they can read.

To make them public: repository → Packages → select the package → Package
settings → Change visibility.

Decide now, because step 3 differs.

---

## Step 1: cluster prerequisites

```bash
kubectl create namespace openoncology-staging
```

You need:

- An ingress controller. The chart assumes **ingress-nginx**; the network policy
  values name its namespace as `ingress-nginx`.
- A default **StorageClass**. Four volumes are claimed: Postgres, Keycloak's
  Postgres, MinIO and Redis.
- **cert-manager** with a `letsencrypt-prod` ClusterIssuer, or change
  `ingress.annotations` and supply your own TLS secret.

Confirm:

```bash
kubectl get storageclass
kubectl get ns ingress-nginx
kubectl get clusterissuer letsencrypt-prod
```

---

## Step 2: create the five secrets

The API refuses to start in staging without a real `SECRET_KEY` and a
`KEYCLOAK_AUDIENCE`. That is deliberate: `config.is_hardened()` treats staging
like production, so a staging deploy exercises production's requirements.

Generate values that are not the defaults:

```bash
NS=openoncology-staging

SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
PG_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
PG_ADMIN=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
MINIO_USER=openoncology
MINIO_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
KC_ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
```

Then:

```bash
# 1. API. KEYCLOAK_AUDIENCE must match the audience mapper created in step 4.
kubectl -n "$NS" create secret generic openoncology-api-secrets \
  --from-literal=SECRET_KEY="$SECRET_KEY" \
  --from-literal=KEYCLOAK_AUDIENCE=openoncology-api \
  --from-literal=MINIO_ACCESS_KEY="$MINIO_USER" \
  --from-literal=MINIO_SECRET_KEY="$MINIO_PASSWORD"

# 2. Postgres, used by the Bitnami sub-chart and by Keycloak's database.
kubectl -n "$NS" create secret generic openoncology-pg-secret \
  --from-literal=password="$PG_PASSWORD" \
  --from-literal=postgres-password="$PG_ADMIN"

# 3. MinIO. Must match the API's MINIO_ACCESS_KEY and MINIO_SECRET_KEY above;
#    nothing in the chart can check that they agree.
kubectl -n "$NS" create secret generic openoncology-minio-secrets \
  --from-literal=MINIO_ROOT_USER="$MINIO_USER" \
  --from-literal=MINIO_ROOT_PASSWORD="$MINIO_PASSWORD"

# 4. Keycloak admin.
kubectl -n "$NS" create secret generic openoncology-keycloak-secrets \
  --from-literal=admin-password="$KC_ADMIN_PASSWORD"

# 5. Backup. An mc alias URL pointing at the in-cluster MinIO.
kubectl -n "$NS" create secret generic openoncology-backup-secrets \
  --from-literal=mc-host-url="http://${MINIO_USER}:${MINIO_PASSWORD}@openoncology-staging-minio:9000"
```

**Record these somewhere.** Losing `SECRET_KEY` invalidates sessions; losing the
Postgres password locks you out of the database, which has no backup until the
CronJob has run at least once.

Optional, if you want the corresponding features: add `STRIPE_SECRET_KEY`,
`RESEND_API_KEY`, `OPENAI_API_KEY` and `ONCOKB_API_TOKEN` to
`openoncology-api-secrets`. Without `ONCOKB_API_TOKEN` the system uses the
curated static table, which is a supported mode rather than a degraded one, but
`EvidenceBaseDegraded` will fire because provenance is correctly recorded as not
current.

---

## Step 3: image pull secret, only if packages are private

Skip if you made them public in step 0.

```bash
kubectl -n "$NS" create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=immortal71 \
  --docker-password=<a PAT with read:packages>
```

Then add to your install:

```
--set global.imagePullSecrets[0].name=ghcr-pull
```

---

## Step 4: Keycloak realm and the audience mapper

Keycloak deploys with the chart, but the realm is not created for you.

1. Reach the admin console at `https://auth.staging.openoncology.org`, logging in
   as `admin` with `KC_ADMIN_PASSWORD`.
2. Create a realm named `openoncology`.
3. Create a confidential client `openoncology-api` and a public client
   `openoncology-web`.
4. **Add an audience mapper** to `openoncology-api`: Client scopes → the
   client's dedicated scope → Add mapper → By configuration → Audience → set
   *Included Client Audience* to `openoncology-api`, and *Add to access token*
   on.

Step 4.4 is the one people miss. Keycloak puts the client id in `azp` and
`"account"` in `aud` by default, so without the mapper every token fails the
audience check added in #130 and the API returns 401 for everything.

Verify a token carries the right audience before installing:

```bash
# after obtaining a token, decode the payload
python -c "import base64,json,sys; p=sys.argv[1].split('.')[1]; print(json.loads(base64.urlsafe_b64decode(p+'==')).get('aud'))" <token>
```

---

## Step 5: install

```bash
helm dependency update infra/helm

helm upgrade --install openoncology-staging ./infra/helm \
  --namespace openoncology-staging \
  -f infra/helm/values.yaml \
  -f infra/helm/values.staging.yaml
```

Watch it come up:

```bash
kubectl -n openoncology-staging get pods -w
```

---

## Step 6: what to check, in this order

Each of these is a control added recently that has never executed.

**Pods start and the API is ready.** Readiness is `/ready`, which round-trips
Postgres and Redis, so a Ready pod means both are reachable.

```bash
kubectl -n openoncology-staging get pods
kubectl -n openoncology-staging exec deploy/openoncology-staging-openoncology-api -- \
  wget -qO- localhost:8000/ready
```

**Every queue has a consumer.** Four worker deployments must exist: `genomic`,
`ai`, `notify`, `gdpr`. The last one is the reason `DELETE /api/me` used to
promise a deletion that never happened.

```bash
kubectl -n openoncology-staging get deploy | grep worker
```

**Beat is scheduling.** Without it neither the GDPR retention sweep nor the
stale-submission recovery ever runs.

```bash
kubectl -n openoncology-staging logs deploy/openoncology-staging-openoncology-beat --tail=20
```

**Object storage answers.** If this fails, every upload fails.

```bash
kubectl -n openoncology-staging exec sts/openoncology-staging-minio -- \
  mc --version
```

**The backup runs.** Do not wait for 02:00; trigger it.

```bash
kubectl -n openoncology-staging create job --from=cronjob/openoncology-staging-openoncology-db-backup backup-test
kubectl -n openoncology-staging logs job/backup-test
```

**Then restore from it.** This is the step that closes `OO-12`, and until
somebody does it, `HIPAA_COMPLIANCE.md` correctly says there is no contingency
plan. `docs/RUNBOOK_BACKUP_RESTORE.md` has the procedure. Staging is exactly
where it should happen.

**Session lifetimes were applied.** The `kcadm` Job runs post-install.

```bash
kubectl -n openoncology-staging logs job/openoncology-staging-openoncology-keycloak-session-policy
```

---

## Step 7: after it works

- **Turn on NetworkPolicies.** `--set networkPolicy.enabled=true`. They are off
  by default because a wrong selector fails closed, and staging is where you
  want to discover that. Check the datastore selectors against
  `kubectl get pod --show-labels` first, because Bitnami's labels vary by
  sub-chart version.
- **Point Prometheus at the alert rules** and set an Alertmanager address.
  `infra/prometheus.yml` leaves `alertmanagers: []` deliberately, because a
  wrong address fails silently: rules evaluate, alerts fire, nothing receives
  them.
- **Cut a release tag** so production has an immutable tag to pin, which is what
  `OO-19` still has open:

  ```bash
  git tag v1.0.0 && git push origin v1.0.0
  ```

  That produces `ghcr.io/immortal71/openoncology/api:v1.0.0`, after which
  `values.production.yaml` can pin it.

---

## If something fails

Most likely, in rough order:

| Symptom | Cause |
|---|---|
| `ImagePullBackOff` | Packages are private and no `imagePullSecret` was set. Step 3 |
| API `CrashLoopBackOff` | `SECRET_KEY` or `KEYCLOAK_AUDIENCE` missing. The log says which |
| Every request returns 401 | The audience mapper in step 4.4 |
| Uploads fail | MinIO credentials do not match between the two secrets |
| Backup job fails | `mc-host-url` wrong, or MinIO not yet ready |
| Pods pending | No StorageClass, or the volumes exceed the cluster's capacity |

Record what actually broke. An install that revealed three misconfigurations is
a successful staging deploy, and the list is worth more than a clean run.
