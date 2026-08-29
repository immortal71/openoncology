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

### OO-15: Two governance controls the compliance guard exposed
- **Why**: `api/tests/test_compliance_claims.py` failed against two further rows once it existed. **Security officer**: the row cited a CODEOWNERS file, and no such file exists at the root, under `.github/` or under `docs/`, so the role is unassigned rather than assigned somewhere else. **Automatic log-off**: the row quoted "30 min idle / 8 hr max" and nothing in this repository sets `ssoSessionIdleTimeout` or `ssoSessionMaxLifespan`, so sessions run at the Keycloak image's defaults, which do not match the figure quoted. Both rows are corrected; these are the gaps behind them.
- **Files**: .github/CODEOWNERS, infra/helm/templates/keycloak.yaml, docs/HIPAA_COMPLIANCE.md
- **Acceptance**:
  - A CODEOWNERS file exists naming a responsible owner, or the row is rewritten to describe how the role is actually held
  - Session lifetimes are set explicitly in the realm configuration the chart deploys, at values someone has chosen, rather than inherited
  - Both rows return to implemented only once `test_compliance_claims.py` passes with them marked so
- **Out of scope**: who the security officer is, which is the maintainer's decision and not a code change
- **Progress 2026-08-29**: session lifetimes are applied by `infra/helm/templates/keycloak-session-policy.yaml`, a post-install and post-upgrade Job running `kcadm`, at the 1800s / 28800s the checklist had been quoting without setting. That half is closed and the row is back to implemented. `.github/CODEOWNERS` now exists, naming review ownership for every guard-protected path and every risk document.
- **Still open**: the security-officer half. A file naming a code owner is not a person accepting the §164.308(a)(2) role. That is an appointment, and it stays at not-implemented until it is recorded somewhere a reviewer can check. Nothing an agent does can close it.
- **Risk**: low to implement. Worth noting that assigning an owner in a file is not the same as a person accepting the role, and the checklist can only ever check the first.

### OO-19: Pin the deployed image tags once images exist
- **Why**: `values.yaml` uses `latest` for the api and web images. That is mutable: a pod restart can change the running version, and nothing records which code produced a given result. For software whose output is clinical evidence this is the same defect as the mutable pipeline container tags in OO-6, on the images that run the ranking. #151 added `publish-images`, which emits an immutable `sha-<short>` on every push to main and a `v*` tag on a git tag, so the tags to pin will exist after the first merge.
- **Not done in #151 on purpose**: no image has been published yet, and pinning a tag that does not exist is worse than pinning a mutable one. It has to follow the first successful publish rather than accompany it.
- **Files**: infra/helm/values.staging.yaml, infra/helm/values.production.yaml, api/tests/test_deployment_manifests.py
- **Acceptance**:
  - `values.staging.yaml` pins `api.image.tag` and `web.image.tag` to a `sha-` tag that exists in the registry
  - `values.production.yaml` pins a `v*` tag
  - A test fails if either file uses `latest`, or omits a tag and so inherits it
  - `values.yaml` may keep `latest`, since it is the base and is never deployed from alone
- **Out of scope**: digest pinning for these two images, which is stricter again and belongs with OO-6's decision about how digests get refreshed
- **Risk**: low. Worth noting the first pin cannot be verified from this repository: whether the tag resolves is a property of the registry.

---

## In progress

<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

---

## In review

<!-- Entry plus PR URL. Cleared by hand when merged. -->

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

### OO-15: Session lifetimes applied; security officer still unassigned
Half closed in [#148](https://github.com/immortal71/openoncology/pull/148). A
`kcadm` Job applies `ssoSessionIdleTimeout` 1800s and `ssoSessionMaxLifespan`
28800s on install and upgrade, which are the figures HIPAA_COMPLIANCE.md had been
quoting without setting. `.github/CODEOWNERS` now exists.

The entry stays in Ready. A file naming a code owner is not a person accepting
the §164.308(a)(2) role, and nothing in a pull request can record an appointment.

### OO-17: The degraded-evidence condition is alertable
Merged in [#147](https://github.com/immortal71/openoncology/pull/147). A counter
beside the log call could not work: the fallback count is a module global in the
ai worker, a separate process from the API with no metrics endpoint, and it
resets on restart, which is when a sustained run would look like it had stopped.
The signal is read from `results.evidence_provenance` by a postgres_exporter
query instead. Two metrics declared in `api/main.py` and never incremented were
removed rather than wired up.

### OO-9: Keycloak's database sized from its own values
Merged in [#146](https://github.com/immortal71/openoncology/pull/146). It read
the application sub-chart's values, so production gave a realm database a 200Gi
volume and resizing one silently resized the other. `volumeClaimTemplates` is
immutable, so applying this to an existing cluster needs a recreate; the runbook
records that next to the note that this database is not backed up.

### OO-16: Exporters deployed, queue depth alertable
Merged in [#145](https://github.com/immortal71/openoncology/pull/145).
`redis_key_size{key="gdpr"}` is the number of erasure requests waiting. Celery
task events had to be enabled for any task metric to exist at all, which is
guarded, because without them every `celery_*` rule evaluates against an absent
series and stays silent.

### OO-18: The chart deploys the object storage it pointed at
Merged in [#144](https://github.com/immortal71/openoncology/pull/144).
`MINIO_ENDPOINT` named `{release}-minio:9000` and nothing created it, so every
upload, report write and object deletion failed, as did the backup job. Found
while scoping OO-5, because a policy cannot grant egress to a pod nothing
creates.

### OO-5: Network policies for the chart, off by default
Merged in [#143](https://github.com/immortal71/openoncology/pull/143). Not a port
of the `infra/k8s` set: that selects on a label `_helpers.tpl` never emits, uses
equality where workers render four component values, and points at Keycloak's
database rather than the application's. All three fail closed and render clean.

### OO-14: A compliance mark must cite something that exists
Merged in [#138](https://github.com/immortal71/openoncology/pull/138).
`api/tests/test_compliance_claims.py` fails the build when a row in
`HIPAA_COMPLIANCE.md` claims implementation and cites a path or mechanism that is
absent. It found two more the moment it existed: the security officer row cited a
CODEOWNERS file that does not exist, and automatic log-off quoted session
timeouts nothing sets. Both corrected; the gaps behind them are OO-15.

The check had two defects of its own before merge, both recorded in the PR. It
read only backticked tokens, so it missed CODEOWNERS entirely. And its evidence
search covered `api/`, so it matched its own pattern list and reported a backup
mechanism present that was not. A check that passes by reading its own source is
the pathology it exists to catch, one level up.

### OO-13: Prometheus rules that can fire, against targets that exist
Merged in [#140](https://github.com/immortal71/openoncology/pull/140).
`rule_files: []` and `alertmanagers: []` meant every metric was collected and no
alert could fire. Adding rules first required correcting the scrape config: four
of seven jobs pointed at exporters deployed nowhere and reported `up == 0`
permanently, which pages continuously once anything watches `up`.

Alertmanager's address is deliberately still unset. A wrong one fails silently.

### OO-12: Nightly database backup, restore not yet exercised
Partially addressed in [#141](https://github.com/immortal71/openoncology/pull/141).
The entry **stays open** in Ready. A `pg_dump` CronJob and
`docs/RUNBOOK_BACKUP_RESTORE.md` exist; nobody has restored from one, so
`HIPAA_COMPLIANCE.md` keeps §164.308 at not-implemented.

### OO-11: BWA-MEM2 rebuilt the reference index every task
Merged in [#139](https://github.com/immortal71/openoncology/pull/139). The
process staged the FASTA and none of the index files beside it, so it rebuilt
what setup had already built, at roughly 30 minutes and 12 GB per task. A missing
index now fails up front naming `download_references.sh`, instead of being
silently absorbed.

### OO-10: Paired-end reads carried from upload to aligner
Merged in [#136](https://github.com/immortal71/openoncology/pull/136). The FASTQ
path processed paired-end data as single-end at every stage and `POST /api/submit`
accepted one of the two files a sequencer produces. Read groups also carried a
constant `SM:patient`, so every BAM claimed the same sample name.

This changes what the pipeline computes, so variant-calling measurements taken
before it are not comparable with any taken after.

### Runbook for closing the variant-calling accuracy gate
Merged in [#134](https://github.com/immortal71/openoncology/pull/134).
`docs/RUNBOOK_VARIANT_CALLING_VALIDATION.md`, scoped to chr20 in NIST confident
regions to match the existing reference figure. Writing it is what found OO-10
and OO-11.

### HIPAA checklist corrected, four controls were never implemented
Merged in [#137](https://github.com/immortal71/openoncology/pull/137) and
[#138](https://github.com/immortal71/openoncology/pull/138). Contingency planning
cited WAL archiving and object-store versioning, neither configured, pointing at
Keycloak's database rather than the application's. Data-at-rest cited PostgreSQL
checksums, which are off.

### OO-4: Refresh the stale figures in the pyproject coverage comment
Merged in [#132](https://github.com/immortal71/openoncology/pull/132). Rebased
onto main after #130 and #131, and re-measured: the figures the branch was
carrying had themselves gone stale by two merges while it sat open. The comment
now carries its date as part of the number, because `fail_under` can be pinned by
a test and a measurement of a moving suite cannot.

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
