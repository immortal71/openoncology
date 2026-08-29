# OpenOncology Backlog

Git-tracked project state. Agents read this at session start and update it at
session end, so work survives context compaction, restarts, and closed laptops.

Sections are ordered by pipeline position. `/next` pulls from the top of
`## Ready`. Nothing pulls from `## Needs human decision`.

---

## Ready

<!-- Populate with /groom "<objective>". Entries use this shape:

### OO-N: Consolidate design tokens into globals.css
- **Why**: Tailwind autocomplete keeps reintroducing generic purple and blue, drifting from the green/cream system
- **Files**: web/app/globals.css, web/tailwind.config.js
- **Acceptance**:
  - Every color in tailwind.config.js references a CSS variable, no literals
  - #0F6E56, #FAFAF8, #16181D, #E4E2DB defined once in globals.css
  - Grep for `purple-`, `blue-`, `cyan-` across web/ returns nothing
  - Build passes, no visual regression on the homepage
- **Out of scope**: component markup, marketplace modal
- **Risk**: low
-->

### OO-5: Port the NetworkPolicy set from infra/k8s into the Helm chart
- **Why**: `infra/k8s/namespace.yaml` carries default-deny plus four allow rules; the chart carries none, and the chart is what production deploys from. Same drift class as the readiness probe and the missing beat Deployment, both fixed on `fix/deployment-and-auth-hardening`. Not fixed alongside them because it cannot be ported verbatim: `allow-workers-egress` selects on `app.kubernetes.io/part-of: openoncology-workers`, and `_helpers.tpl` never emits that label, so the rule as written selects nothing. Shipping a default-deny policy whose allow rules match no pods severs every worker from Postgres and Redis, and it renders and lints clean.
- **Files**: infra/helm/templates/networkpolicy.yaml, infra/helm/templates/_helpers.tpl, infra/helm/values.yaml, api/tests/test_deployment_manifests.py
- **Acceptance**:
  - Every allow rule's selector matches labels the chart actually emits, verified against `helm template` output rather than read off the k8s copy
  - Worker, beat, api and web pods each keep egress to Postgres, Redis and 443
  - A test asserts every NetworkPolicy podSelector matches at least one rendered pod
  - `helm template` output passes kubeconform in the `validate-manifests` job
- **Topology found while scoping this, and it invalidates a verbatim port**: the chart runs *two* Postgres instances. `values.yaml` enables the Bitnami `postgresql` sub-chart and `openoncology.databaseUrl` points the app at `{release}-postgresql`; separately `templates/postgres.yaml` renders an ungated StatefulSet at `{fullname}-postgres` carrying `component: postgres`, and that one is Keycloak's database (`keycloak.yaml:32`). So an egress rule allowing `component: postgres` reaches Keycloak's database and not the application's. The Bitnami pods carry Bitnami's labels, not this chart's, and those differ by sub-chart version. Redis is Bitnami-only; there is no chart-local template for it.
  Workers also render four distinct component values (`worker-genomic`, `worker-ai`, `worker-notify`, `worker-gdpr`), so one selector cannot match them by `component` and needs either a shared label or `matchExpressions`.
  The gdpr worker needs egress the others do not: it calls Keycloak's admin API to delete users and MinIO to delete objects (`workers/gdpr_worker.py`). A policy modelled on the other three silently breaks erasure, which is the obligation #130 just restored.
- **Recommended shape**: gate the whole set behind `networkPolicy.enabled`, default **false**. A wrong policy fails closed, there is no cluster to test against here, and default-on means the first person to find out is whoever deploys it. Drive the datastore selectors from values so an operator can match their actual sub-chart labels.
- **Out of scope**: the raw `infra/k8s` manifests, which already have this
- **Risk**: medium — a wrong policy fails closed and silently

### OO-6: Pin the pipeline's container images by digest
- **Why**: `pipeline/modules/*.nf` pin containers by tag (`broadinstitute/gatk:4.5.0.0`, `etal/cnvkit:0.9.10`, `docker.io/szarate/manta:1.6.0`, two biocontainers). A tag is mutable. The variant-calling validation gate asks which pipeline produced a call set, and a tag cannot answer it: the same tag six months apart is a different image and possibly different calls. `nextflow.config` now declares `gatk_version` once, so the GATK pair can no longer diverge, but neither is pinned to an immutable reference.
- **Files**: pipeline/nextflow.config, pipeline/modules/*.nf, api/tests/test_pipeline_config.py
- **Acceptance**:
  - Every `container` directive resolves to a `name@sha256:...` reference
  - Digests are recorded with the date and the tag they resolved from, so a later bump is auditable
  - A test asserts no `container` directive uses a bare tag
  - The conda specs stay pinned to the same tool versions the digests correspond to
- **Out of scope**: the conda-only modules, which pin exact versions already; choosing different tool versions
- **Risk**: low

### OO-9: Keycloak's database is sized by the application database's setting
- **Why**: `templates/postgres.yaml` is Keycloak's database, not the application's, which uses the Bitnami `postgresql` sub-chart. Its `volumeClaimTemplates` requests `.Values.postgresql.primary.persistence.size`, the sub-chart's value. `values.production.yaml` sets that to 200Gi, so Keycloak's realm database, a few megabytes of users and clients, claims a 200Gi volume, and anyone resizing the application database silently resizes Keycloak's too. Found while scoping OO-5.
- **Files**: infra/helm/templates/postgres.yaml, infra/helm/values.yaml, infra/helm/values.production.yaml
- **Acceptance**:
  - Keycloak's database size comes from its own value, defaulted to something proportionate
  - The two databases are distinguishable by name or comment, so the next reader does not assume `postgres.yaml` is the application's
  - `helm template` still renders and passes kubeconform
- **Out of scope**: consolidating the two databases, which is a data-migration decision rather than a chart one
- **Risk**: low to change, but note `volumeClaimTemplates` is immutable on an existing StatefulSet, so an in-place `helm upgrade` will reject the edit. The entry is only safe on a fresh install or with a documented recreate step, and that caveat is the reason it is filed rather than done in passing.

### OO-10: The FASTQ path aligns paired-end reads as single-end
- **Why**: `main.nf:116` channels the input with `Channel.fromPath`, not `fromFilePairs`; `trimmomatic.nf` runs `trimmomatic SE` against `TruSeq3-SE.fa`; `bwa_mem2.nf` passes one read file to `bwa-mem2 mem`. Nothing pairs a mate file at any point. Essentially all clinical sequencing is paired-end, and so is the GIAB HG002 data the 3.1 validation gate is measured against, so mate-pair information is discarded exactly where it resolves the repetitive regions in which variants are missed. Found while writing `docs/RUNBOOK_VARIANT_CALLING_VALIDATION.md`, and it is why that runbook recommends the BAM route first.

  This is not only a validation-path problem. `POST /api/submit` accepts a single `dna_file` described as "VCF, FASTQ, or BAM", so a clinician holding the two files every sequencer emits can upload only one of them, and nothing says so. The result is a real sample aligned single-end with half its reads absent, reported with the same confidence as any other. That puts this on the clinical intake path rather than the benchmark path, and raises it above the other Ready entries.
- **Files**: pipeline/main.nf, pipeline/modules/trimmomatic.nf, pipeline/modules/bwa_mem2.nf, api/routes/submit.py
- **Acceptance**:
  - A paired FASTQ input is consumed as one sample, not as two independent runs
  - Trimmomatic runs `PE` with paired adapters, and its unpaired outputs are handled deliberately rather than dropped by accident
  - `bwa-mem2 mem` receives both mates
  - Single-end input still works, or its removal is a stated decision rather than a side effect
  - A test asserts a paired input produces one BAM per sample
  - `POST /api/submit` either accepts a mate pair, or states plainly that it does not and what that costs
- **Out of scope**: the somatic and RNA-seq paths, beyond what falls out of the same change
- **Risk**: medium. This changes what the pipeline computes, so it invalidates any variant-calling measurement taken before it. Either sequence it ahead of the run in the runbook, or record which configuration produced which number.

### OO-11: BWA-MEM2 rebuilds the reference index on every alignment task
- **Why**: `BWA_MEM2_ALIGN` declares `path ref_fasta` as its only reference input, so Nextflow stages the FASTA into the task work directory and none of the index files beside it. The script then runs `bwa-mem2 index $ref_fasta`, which `pipeline/scripts/download_references.sh` puts at roughly 30 minutes and 12 GB of RAM, and the result is discarded with the work directory. Setup builds the index and the pipeline never sees it, so every sample pays the cost again and every retry pays it once more.
- **Files**: pipeline/modules/bwa_mem2.nf, pipeline/main.nf
- **Acceptance**:
  - The index files are staged as inputs alongside the FASTA
  - `bwa-mem2 index` is gone from the alignment script, or runs only when the index is genuinely absent
  - A missing index fails with a message pointing at `download_references.sh`, rather than silently costing half an hour
- **Out of scope**: whether to ship or cache a prebuilt index, which is a distribution decision
- **Risk**: low

### OO-12: There is no backup of patient data, and the compliance checklist said there was
- **Why**: Nothing in this repository backs up the application database or object storage. No `archive_mode`, `archive_command` or `wal_level`; no MinIO versioning; no `pg_dump`, pgBackRest, wal-g or Velero anywhere. The Bitnami `postgresql` sub-chart has persistence, and persistence is not backup: a deleted PVC, a bad migration or a ransomware event loses every submission, mutation and result permanently, with no recovery path. `HIPAA_COMPLIANCE.md` carried ✅ against §164.308 contingency planning, citing "PostgreSQL WAL + MinIO versioning (see `infra/helm/postgres.yaml`)", and that file is Keycloak's database rather than the application's. The claim has been corrected; the gap it was covering is this entry.
- **Files**: infra/helm/values.yaml, infra/helm/values.production.yaml, infra/helm/templates/, docs/HIPAA_COMPLIANCE.md, docs/SETUP.md
- **Acceptance**:
  - The application database has scheduled backups with a stated retention, and object storage has versioning or an equivalent
  - A **restore** has been performed into a scratch namespace and the result checked, because an unexercised backup is a belief rather than a control
  - RPO and RTO are written down, even if the numbers are modest
  - `HIPAA_COMPLIANCE.md` moves to ✅ only after that restore, and names what was restored and when
- **Out of scope**: choosing a managed database, which is a hosting decision
- **Progress 2026-08-29**: nightly `pg_dump` CronJob added to the chart, enabled by default, writing to object storage with a manifest and 30 day retention, plus `docs/RUNBOOK_BACKUP_RESTORE.md`. The entry **stays open**: its acceptance requires an exercised restore, and nobody has run one. Object storage versioning is still absent, so a database-only restore yields rows referencing missing files, and Keycloak's database is still unbacked.
- **Risk**: high while open. This is the one entry where the failure mode is unrecoverable rather than merely wrong. Lower than it was, since a dump now exists; not closed, because a backup nobody has restored is a belief about a file.

### OO-14: A compliance ✅ should have to cite something that exists
- **Why**: Two rows in `HIPAA_COMPLIANCE.md` carried ✅ against controls that were never implemented, one citing a file that is a different database. Both read as verified for as long as nobody checked. This is the same shape as the coverage-threshold drift that OO-3 closed with a test, and the same shape as F11, F14 and F18: an assertion about something present, with nothing asserting the absence. The document is the one a compliance officer would be handed.
- **Files**: api/tests/test_compliance_claims.py, docs/HIPAA_COMPLIANCE.md
- **Acceptance**:
  - Every ✅ row whose Implementation cites a repository path is checked: the path exists
  - Where a row cites a specific mechanism that is greppable (`archive_mode`, `data_checksums`, an env var, a middleware module), the test asserts it is actually present
  - Rows that cannot be checked mechanically are listed explicitly with the reason, the way `test_marketplace_phi_disclosure.py` handles its exemptions, so the uncheckable set is visible rather than implied
  - The test fails today against the pre-correction version of the document
- **Out of scope**: the substance of HIPAA compliance, which is a legal question and not a test
- **Risk**: low

### OO-16: Deploy the exporters the monitoring config was scraping
- **Why**: `infra/prometheus.yml` scraped `db-exporter:9187`, `redis-exporter:9121` and `worker-*:9100`. None of the first two exists in `docker-compose.yml` or the Helm chart, and nothing in `api/workers/` starts a metrics server, so port 9100 is not listening. All four reported `up == 0` permanently, invisibly, because nothing alerted on `up`. Those jobs are commented out rather than deleted, since the intent is right and the deployment is what is missing. `api/tests/test_alert_rules.py` now fails if a scrape job names a host no deployment defines.
- **Files**: docker-compose.yml, infra/helm/templates/, infra/prometheus.yml, api/workers/__init__.py
- **Acceptance**:
  - postgres_exporter and redis_exporter are deployed in both deployment paths, or the jobs stay commented and the reason is recorded here
  - Celery workers expose a metrics endpoint, or the celery-exporter is deployed against the broker instead
  - Each job is uncommented only once its exporter is actually reachable, and `test_alert_rules.py` passes with it active
  - Queue depth and task age on `genomic` and `gdpr` become alertable, which is what OO-13 could not cover
- **Out of scope**: dashboards
- **Risk**: low

### OO-17: The degraded-evidence alarm emits no metric, and two metrics emit nothing
- **Why**: `settings.degraded_evidence_alert_after` escalates a **log line** to ERROR after a run of static-fallback resolutions. That is the control risk_analysis open action 4 closed, and it can only be seen by someone reading logs: there is no metric, so it cannot alert. Separately, `api/main.py` declares `openoncology_mutations_processed_total` and `openoncology_genomic_pipeline_seconds` and neither is ever incremented, so both are permanently absent from `/metrics`. A rule written against either would look like coverage and never fire, which is why `test_alert_rules.py` rejects them.
- **Files**: api/main.py, api/services/oncokb_evidence.py, api/workers/genomic_worker.py, infra/alerts/openoncology.rules.yml
- **Acceptance**:
  - A counter or gauge reflects consecutive static-fallback resolutions, and an alert fires on a sustained run
  - The two declared metrics are either incremented at the points they describe, or removed
  - `test_alert_rules.py`'s allowed-metric set grows only alongside the code that emits them
- **Out of scope**: what the alert threshold should be, which is the same policy question as `degraded_evidence_alert_after` itself
- **Risk**: low to implement. Worth noting the evidence path is adjacent to ranking, so the metric should be emitted where the fallback is already logged rather than anywhere new.

---

## In progress

<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

---

## In review

<!-- Entry plus PR URL. Cleared by hand when merged. -->

### OO-4: Refresh the stale figures in the pyproject coverage comment
- **Why**: The comment moved into `[tool.coverage.report]` by OO-2 cites 53.93% over 8,353 production statements with 844 api tests. The suite has grown since: it now measures about 61% over 8,798 statements with 1,102 api tests. Anyone reading the comment concludes the gate sits a point below the measured total, when it actually sits nine points below, so the gate catches less than the comment claims it does.
- **Files**: pyproject.toml
- **Acceptance**:
  - The comment cites the current measured coverage, statement count and api test count, taken from an actual local run rather than copied from this entry
  - The narrative explaining why the number moved 63, 69, 52 is preserved, not replaced
  - `fail_under` itself is unchanged at 52
  - `make test-backend` still passes
  - `pytest api/tests/test_coverage_threshold_consistency.py` still passes
- **Out of scope**: changing the threshold; the `omit` list; README and CONTRIBUTING, which quote the gate rather than the measurement.
- **Risk**: low

**PR**: [#132](https://github.com/immortal71/openoncology/pull/132). Rebased onto
`main` after #130 and #131 merged, and the figures re-measured: the ones the
branch was carrying had themselves gone stale by two merges while it sat open.

---

## Needs human decision

<!-- Anything an agent declined to do unattended: guard-hook blocks, validator
     BLOCKs, mis-scoped entries, and anything the planner marked
     Risk: scientific. This section is the safety valve. When it grows, that is
     the system working, not failing. -->

### OO-7: Decide whether `civic_supplement_enabled` should default to True
- **Why**: Asked as "how do we raise the benchmark", and the measurements already
  in the repository answer it in a way that rules ranking work out. In
  `hard_benchmark_results.json`, three of five difficulty buckets sit exactly on
  their own ceiling — MULTI_DRUG 0.9792/0.9792, LOW_PURITY 0.7778/0.7778,
  REFRACTORY 0.5476/0.5476. A ceiling is the best any reordering of the existing
  candidate pool could score, so for those buckets a better ranker scores
  identically. The only headroom left is 0.033 in CONFLICTING_EVIDENCE and 0.024
  in RARE_OR_COMPLEX, under a point of aggregate P@3.

  What moves the ceiling is evidence coverage, and
  `validation_results/civic_coverage_gain.json` has already measured the one
  lever that exists: loading CIViC level A/B predictive evidence makes 3 of the
  13 missed NCI-MATCH arms reachable and leaves 10 absent. The flag exists and
  is off.

  Not an agent's call. Widening the actionability table changes which drugs the
  system can recommend, `candidate_pool_policy` is `evidence_first` so the table
  decides the pool wherever it has an answer, and the audit's own caveat is that
  reachable is not correct. It is also the wrong metric to optimise against
  alone: open action 2 is still the unresolved question, and P@3 against a
  curated key shares sources with the table being widened.
- **Risk**: scientific
- **Evidence to weigh**: `validation_results/civic_coverage_gain.json`,
  `hard_benchmark_results.json` `by_difficulty` ceilings, risk_analysis.md §7 and
  open action 2. The holdout-50 set scores standard P@3 0.5083 against the hard
  benchmark's 0.8009; whichever way this goes, both numbers should move together
  or the gap needs explaining.

### OO-8: `require_current_evidence` must be True before any clinical deployment
- **Why**: `api/config.py` says so in its own comment — "It MUST be True for any
  clinical deployment" — and it defaults False, correctly, because this is
  research-use software. Recorded here so the flip is a decision someone makes
  rather than one someone forgets. It pairs with the new production requirement
  for `KEYCLOAK_AUDIENCE`: both are settings whose safe research default is the
  unsafe clinical one.
- **Risk**: scientific / policy — this is a hazard control, not a config tidy

---

## Done

<!-- Merged entries, newest first. Trim periodically. -->

### Intended use stated on every output path
Merged in [#131](https://github.com/immortal71/openoncology/pull/131), recorded as
F18 in [risk_analysis.md](docs/risk_analysis.md). The FHIR export carried no
research-use marker and reported `status: final`, which in FHIR R4 means complete
and verified; the only thing verified was that the pipeline had finished. Unreviewed
reports are now `preliminary`. The results payload's only disclaimer lived inside
`patient_summary`, which fails to None, so it vanished exactly when generation went
wrong and the response still carried drug names and OncoKB levels. `intended_use` is
now a top-level typed field with conservative defaults.

Labelling is not validation. Nothing here moves a gate in `REGULATORY_FRAMEWORK.md`
section 3.

### Deployment path: unconsumed gdpr queue, missing beat, readiness probe, JWKS auth
Merged in [#130](https://github.com/immortal71/openoncology/pull/130). Four absences
that no check could catch because every check asserted a positive about something
present. `task_routes` sent erasure tasks to a `gdpr` queue nothing consumed, so
`DELETE /api/me` promised deletion within 30 days and the message sat in Redis. The
chart had no Celery Beat, so neither periodic task had ever fired in Kubernetes. The
readiness probe asked `/health`, which answers 200 unconditionally. Auth refetched
one Keycloak key per request and passed `audience` with `verify_aud: False`.

A `validate-manifests` job now renders the chart through kubeconform. Its first
version passed in eight seconds having rendered nothing: helm's dependency error went
to stderr, kubeconform read empty stdin and reported "Valid: 0", and the pipe returned
kubeconform's status. Fixed in the same PR under `pipefail` with assertions on the
rendered output, which is the section 7 lesson arriving inside the commit that was
about the same failure.

### OO-3: Add a drift guard test for the coverage threshold
Merged in [#128](https://github.com/immortal71/openoncology/pull/128).
`api/tests/test_coverage_threshold_consistency.py` reads `fail_under` from
`pyproject.toml` and fails the build if the README badge, the `CONTRIBUTING.md`
prose, or a `--cov-fail-under` literal in `Makefile` or `ci.yml` disagrees with it.

The badge is checked in both representations it carries on one line, URL-escaped
and ASCII. Verified by breaking only the URL form and leaving the alt text correct:
a check written against a single representation passes that edit with the badge
visibly wrong, which is the shape the original 62 drift took.

### OO-2 follow-up: CONTRIBUTING.md falls out of step with CI
Merged in [#127](https://github.com/immortal71/openoncology/pull/127) alongside OO-2
itself, plus `CONTRIBUTING.md:306` in the reconcile that followed. The entry was
raised because `CONTRIBUTING.md` sat outside OO-2's declared **Files** list, and
widening scope silently is what that list exists to prevent. Both mentions now point
at `pyproject.toml` as the source of the number instead of quoting a flag CI no longer
passes.

### OO-2: Single-source the backend coverage threshold in pyproject.toml
Merged in [#127](https://github.com/immortal71/openoncology/pull/127) as `ba6c04a`.
`[tool.coverage.report] fail_under = 52` now declares the gate once; `Makefile` and
`ci.yml` inherit it, and the api-suite invocation keeps its explicit
`--cov-fail-under=0` because coverage is only complete after the second run appends.
Verified locally at 1102 + 42 tests passing, 61% total against the 52 gate.

One consequence to remember: any `pytest --cov=...` run now inherits the gate unless
it opts out, so a single suite on its own reports around 14% and exits non-zero with
every test passing. `CONTRIBUTING.md` documents this.

### OO-1: Correct the stale 62% coverage figures in README and CONTRIBUTING
Merged in [#124](https://github.com/immortal71/openoncology/pull/124) as `fd2bf89`.
The README badge and both `CONTRIBUTING.md` mentions moved from 62 to 52, in every
representation the badge carries (the URL-escaped `%E2%89%A5` segment and the ASCII
`>=` alt text). The `0.625` Precision@3 ceiling elsewhere in the docs is an unrelated
number and was confirmed untouched.
