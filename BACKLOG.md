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

---

## In progress

<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

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
