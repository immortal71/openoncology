# Runbook: database backup and restore

**What exists.** A CronJob (`infra/helm/templates/backup-cronjob.yaml`) takes a
nightly `pg_dump` of the application database, gzips it, and writes it to object
storage with a manifest recording the timestamp, database and byte count.
Retention is 30 days by default.

**What does not exist yet, and why OO-12 stays open.** Nobody has performed a
restore. Until someone has, this is a job that produces files, not a contingency
plan. `HIPAA_COMPLIANCE.md` keeps §164.308 at not-implemented until the drill in
this document has been run and dated, which is deliberate: the previous version
of that row was marked satisfied on the strength of an intention.

---

## What is and is not covered

| Data | Covered | Notes |
|---|---|---|
| Application database | Yes | Nightly logical dump |
| Keycloak database | **No** | A separate PostgreSQL (`templates/postgres.yaml`). Losing it loses user accounts and the realm, though not patient data. See OO-9 |
| Object storage: raw uploads, VCFs, reports | **No** | Versioning is still not enabled. The dump carries the database rows that reference these objects, so a database-only restore yields records pointing at absent files |
| Redis | No, by design | Broker and cache. Losing it loses in-flight tasks, which are `acks_late` and redeliverable |

The second and third rows are gaps, not decisions. They are recorded here rather
than left for someone to discover mid-incident.

## Recovery objectives

Not yet agreed. Stating the implied ones so they can be argued with:

- **RPO**, worst-case data loss: up to 24 hours, set by the nightly schedule.
- **RTO**, time to restore: unmeasured. The drill below is what measures it.

A 24 hour RPO is a decision someone should make deliberately for clinical data,
not inherit from a default cron expression.

---

## Verify a backup exists and is plausible

Do this weekly. It takes a minute and is the only thing standing between a
believed backup and a real one.

```bash
mc ls store/openoncology-backups/db/ | tail -5
mc cat store/openoncology-backups/db/<STAMP>.manifest.json
```

The manifest records the byte count the job measured. Compare it against the
object's actual size:

```bash
mc stat store/openoncology-backups/db/<STAMP>.sql.gz
```

A mismatch means a truncated upload. The job aborts on a dump under 1 KiB, so a
missing database produces a failed job rather than a small file, but a partial
upload is not something the job can detect from inside.

## Restore drill

Run into a scratch namespace or a local container. Never into production as a
first attempt.

```bash
mc cp store/openoncology-backups/db/<STAMP>.sql.gz ./restore.sql.gz

docker run -d --name restore-test \
  -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=openoncology \
  -e POSTGRES_USER=openoncology postgres:16

gunzip -c restore.sql.gz | docker exec -i restore-test \
  psql -U openoncology -d openoncology
```

Then check the restore is a database and not merely a successful command:

```bash
docker exec restore-test psql -U openoncology -d openoncology -c "
  SELECT
    (SELECT count(*) FROM submissions) AS submissions,
    (SELECT count(*) FROM mutations)   AS mutations,
    (SELECT count(*) FROM results)     AS results,
    (SELECT max(version_num) FROM alembic_version) AS schema_version;
"
```

Three things to confirm, in this order:

1. **Row counts are non-zero and roughly match production.** A dump that
   restores cleanly and is empty is the failure this is looking for.
2. **`alembic_version` matches the migration head the application expects.** A
   dump from before a migration restores into a schema the running code cannot
   use. Compare against `python scripts/check_migration_chain.py`.
3. **Object references resolve.** Take a handful of `submissions.dna_s3_key`
   values and confirm the objects exist. They will not, if object storage was
   lost too, and that is the gap in the table above rather than a restore
   failure.

Record the date, the dump restored, the row counts and the elapsed time. That
elapsed time is the RTO, and it is the number this document currently cannot
state.

## Restoring into production

Only after the drill has been run at least once.

1. Stop the API and every worker, so nothing writes during the restore. Scale
   the `api`, `worker-*` and `beat` deployments to zero.
2. Confirm the target database is the one you mean. There are two PostgreSQL
   instances in this chart and the application's is the Bitnami sub-chart at
   `{release}-postgresql`, not `{release}-openoncology-postgres`, which is
   Keycloak's.
3. Restore into a fresh database, not over the live one. Rename the damaged
   database rather than dropping it; it may be the only copy of anything the
   backup missed.
4. Run `alembic upgrade head` if the dump predates the deployed code.
5. Bring workers up before the API, so the queues drain before new work arrives.

## Known limitations

- Logical dumps, so no point-in-time recovery. The most recent 24 hours of
  writes are lost in a total-loss scenario. WAL archiving would fix this and
  belongs to the Bitnami sub-chart's configuration.
- The backup image is pinned by tag, not digest, so the tool versions can move
  under a restore. Same class as OO-6 for the pipeline containers.
- Nothing alerts on a failed backup. The CronJob fails loudly in Kubernetes, and
  Kubernetes tells nobody. `OO-16` deploys the exporters that would make
  `kube_job_failed` alertable.
