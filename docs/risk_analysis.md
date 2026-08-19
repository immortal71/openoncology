# Risk Analysis

**Scope of this document.** OpenOncology's output is a ranked list of cancer
drugs for a specific patient's variants. The dominant hazard is therefore not
downtime or data loss, it is a **wrong or absent recommendation that a reader
believes**. This document covers that hazard class. Infrastructure, PHI and
vendor risk are in [Security and privacy risk](#8-security-privacy-and-vendor-risk)
at the end, and in [HIPAA_COMPLIANCE.md](HIPAA_COMPLIANCE.md).

**Status.** Research use only. Every clinical validation gate in
[REGULATORY_FRAMEWORK.md](REGULATORY_FRAMEWORK.md) section 3 is currently
unmet, so this analysis describes hazards in a system that must not be used to
inform treatment. It is written now, before deployment, because several of the
findings below were live defects discovered by writing it.

**Method.** Every finding is traced to code or to a measured result in this
repository. Nothing here is asserted from clinical doctrine. Where a hazard is
real but unquantified, it is listed as unquantified rather than given an
invented likelihood.

**Citations.** References name a file and a symbol, not a line number. An
earlier revision cited line ranges; one of them had already drifted onto
unrelated code, which is the failure mode this document is otherwise built to
avoid. A symbol survives edits above it, and a rename breaks the reference
instead of leaving it pointing at whatever now occupies those lines.

---

## 1. Hazard classes

| # | Hazard | Clinical consequence | Worst case |
|---|---|---|---|
| H1 | Recommends a drug the variant confers resistance to | Patient receives a therapy predicted to fail; effective options delayed | Direct harm |
| H2 | Fails to surface an actionable variant that is present | Patient does not receive an available targeted therapy | Direct harm by omission |
| H3 | A lookup failure is presented as a negative result | Reader concludes "nothing actionable" when nothing was actually checked | Direct harm by omission |
| H4 | Recommendation served from a stale or unversioned evidence base | Advice reflects superseded actionability | Indirect harm |
| H5 | Benchmark figures overstate performance | Adoption decisions made on unsupported evidence | Systemic |
| H6 | Variant calling error upstream of everything | All downstream reasoning is applied to a variant the patient does not have | Direct harm |

H5 is not hypothetical for this project. See section 7.

---

## 2. Findings, verified in code

### F1. Resistance evidence never reached the ranker (H1) — FIXED

`api/workers/ai_worker.py` built a `resistance_context` for `rank_candidates`
by testing `top_mutation.oncokb_level.value in ("LEVEL_R1", "LEVEL_R2")`. The
`OncoKBLevel` enum in `api/models/mutation.py` stores `"R1"` and `"R2"`, not
`"LEVEL_R1"`. The branch could not be taken. `rank_candidates` was called
with `resistance_context=None` on every run, so a variant conferring resistance
never demoted the drug it confers resistance to.

Compounding it, `_query_oncokb` read only `highestSensitiveLevel` from the
OncoKB response and discarded `highestResistanceLevel`, so a resistance-only
annotation arrived as `unknown`. `OncoKBClient.oncokb_level` in
`api/services/oncokb.py` reads both fields; the worker's own inline client did
not.

The module docstring of `api/services/oncokb_evidence.py` states the design
intent this violated:
*"Afatinib is LEVEL_R1 for EGFR T790M, this must be surfaced even if the live
API is unavailable. The table's resistance entries act as a safety floor, never
a ceiling."* The floor existed in one code path and not in the one the worker
used.

Fixed by mapping the wire format onto the enum, comparing enum to enum, and
carrying the resistance level separately from the stored level so a variant that
is sensitive for one drug and resistant to another keeps both.
Regression tests: `api/tests/test_ai_worker_oncokb_levels.py`.

**Residual risk.** The floor now applies on both paths, but it is only as
complete as the static table's resistance entries. A resistance marker that is
absent from that table and unavailable from the live API still fails to demote
anything, and nothing measures how much of known resistance the table covers.

### F2. No variant was ever marked targetable on the OncoKB path (H2) — FIXED

Same root cause. `_query_oncokb` returned the wire string `"LEVEL_1"`, which was
assigned to `Mutation.oncokb_level` and then tested against enum members. The
comparison was always False, so `is_targetable` was never set and
`targetable_mutations` stayed empty, which skips the entire drug repurposing
step that depends on it.

`OncoKBLevel("LEVEL_1")` raises `ValueError`, so the assignment was also invalid
against the `SAEnum` column backing `Mutation.oncokb_level`.

**Why this was invisible:** `_query_oncokb` returns `None` immediately when no
OncoKB token is configured (`api/workers/ai_worker.py`, token check), which is
the default. The defect only activates once a deployment configures a real
token, which is precisely when the evidence starts being relied on. Tests passed
throughout because no test exercised `_query_oncokb` or `resistance_context`.

**Residual risk.** The wire-format-to-enum mapping is pinned by tests, but no
test runs `_query_oncokb` against a real OncoKB response. If the upstream field
names change, the same class of defect returns and the token check still hides
it from every deployment that has no token. The rate at which actionable
variants are missed stays unquantified until open action 2.

### F3. A failed evidence lookup is indistinguishable from no evidence (H3) — FIXED

When `_query_oncokb` returns `None` because the token is missing, the network
failed, or the API rate limited, the mutation is skipped and the report is
assembled without it. Nothing in the output distinguishes *"this variant has no
actionable evidence"* from *"we could not determine whether it does"*. These are
clinically opposite statements.

Now logged explicitly with the affected genes and the warning that absence of
evidence is not established.

The failure state is now also carried out of the service. When the live lookup
fails, `get_all_drugs_for_variant_live_with_metadata` returns an
`evidence_provenance` block whose `is_current` is `False` alongside the drug
levels, so a caller receives the answer and the reason to distrust it in the
same object rather than having to infer one from a log line.

**Closed 2026-08-19.** `mutations.evidence_lookup_status` (migration `0014`)
records per variant whether its actionability lookup succeeded, was never
attempted because no evidence source is configured, or failed. The column is
nullable, so variants written before it existed read as unrecorded rather than
as checked. `_query_oncokb_with_status` supplies the reason;
`_query_oncokb` keeps its old signature so existing callers are untouched. The
oncologist report prints a warning line against any gene whose lookup did not
answer, and `api/tests/test_evidence_lookup_status.py` pins that a failed and a
successful lookup never render alike.

**Residual risk.** Only the OncoKB path sets the field. A variant annotated
solely from the static table carries no lookup status, so "unrecorded" currently
covers both a pre-migration row and a path that never learned to record one.

### F4. Evidence-base provenance is not retained or surfaced (H4) — FIXED

`_bootstrap_oncokb_public_table` and `ensure_oncokb_table_loaded` in
`api/services/oncokb_evidence.py` resolve the actionability table through one of
three paths, and recorded which one only as a log line:

| Path | Meaning |
|---|---|
| `fresh_cache` | Cached OncoKB dump, up to `_ONCOKB_CACHE_MAX_AGE_DAYS = 7` days old |
| `download` | Current OncoKB public dump |
| `static_fallback` | Hardcoded table in this repo, no version, no date |

The chosen path is never stored as state and never returned to a caller.
`get_all_drugs_for_variant_live_with_metadata` returns `drug_levels`,
`gene_fallback_drugs`, `known_actionable_gene` and `alphamissense_score`, and
nothing about where the evidence came from or how old it is.

This is live, not theoretical: during benchmark runs on 2026-08-13 every OncoKB
public dump URL returned `401 Unauthorized` and the service fell back to the
static table on every invocation. Recommendations were produced normally.

**Fixed.** The resolved path and cache timestamp are retained as module state by
`_record_evidence_provenance`, exposed by `get_evidence_provenance()`, and
returned in the evidence metadata from every return path of
`get_all_drugs_for_variant_live_with_metadata`. The static-fallback branch now
logs at `WARNING` rather than `INFO`, with the reason it matters, so the
degraded state is visible in ordinary log review instead of being one `INFO`
line among thousands.

Provenance is stamped onto the result at the moment the recommendation is
produced (`results.evidence_provenance`, migration `0013`), not read at request
time. The table can be refreshed between producing a result and reading it, and
the question a reader is asking is which snapshot produced *this* recommendation.

The API response carries `evidence_provenance` unconditionally. It defaults to
`path="not_recorded"` with `is_current=False`, so a result predating this reads
as provenance-unknown rather than being retroactively claimed to have used
current evidence — the same asymmetry the QC column uses. `is_current` is
`False` for exactly one path, `static_fallback`, which is the undated built-in
table.

**Closed 2026-08-19.** Both halves are now implemented.
`enforce_evidence_policy()` is called where recommendations would be persisted
and raises `DegradedEvidenceError` when the table is not current and
`require_current_evidence` is set. The setting defaults to False, because
refusing to answer is the right clinical posture and the wrong research one, and
this is research-use software; it must be True for any clinical deployment.
When it is False the run still proceeds, but the result records
`recommendations_withheld` and the reason, so an empty recommendation list
produced by policy never reads like one produced because nothing scored. A
sustained run of degraded resolutions escalates from `WARNING` to `ERROR` after
`degraded_evidence_alert_after` consecutive fallbacks, because the hazard was
never one bad resolution, it was weeks of them passing unnoticed.

**Residual risk.** The policy keys on `is_current` alone. A fresh cache one hour
inside the seven-day window and one hour outside it are treated as opposite,
which is the right shape but an arbitrary cliff, and nothing yet measures how
much actionability actually changes across that window.

### F5. Concordance benchmark was circular (H5) — FIXED

`scripts/build_concordance_labels.py` derived each patient's biomarker from the
drug they received, guaranteeing agreement. Detailed in
[ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md](ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md).
Fixed in PR #93; `scripts/detect_label_circularity.py` gates against
reintroduction. The 100% figure is retracted.

**Residual risk.** The gate checks the label-construction script; it cannot
check an answer key built some other way. Retracting the figure also left no
concordance measurement at all, so the claim is gone and the evidence that would
replace it is open action 2.

### F6. Variant calling is unvalidated (H6) — OPEN

Every recommendation is conditioned on the variant call being correct, and no
accuracy measurement exists. `REGULATORY_FRAMEWORK.md` section 3.1 sets the
target at sensitivity ≥ 99% and PPV ≥ 95% against orthogonal WGS, status
"Not completed". Until this is measured, the error rate of the entire pipeline
is unbounded, because no amount of correct downstream reasoning survives a wrong
input variant.

Since 2026-08-19 the measuring instrument exists:
`scripts/validate_variant_calling.py` compares a query VCF against the GIAB
HG002 v4.2.1 GRCh38 benchmark inside NIST's high-confidence regions, stratified
into SNVs and indels, and `api/tests/test_variant_calling_validation.py` pins
its comparison engine, including a case that reproduces the F8 defect and
asserts the harness reports it as loss rather than as agreement. The gate is
blocked on a machine with `bwa-mem2`, `gatk` and a reference genome, not on
anything left to design.

Its `--via-parser` mode, which holds the caller constant at perfect and measures
only ingestion, reported no loss across 83,325 GIAB chr20 variants. That is a
ceiling on end-to-end accuracy, not a measurement of it, and chr20 exercised
only one of the three ingestion paths the score appears to cover: 953
multi-allelic records ran through the F8 path, while zero rejected and zero
malformed records left F7 and the record guards untested. That is the section 7 rule applied to a
run rather than to a benchmark, so the script reports which paths its input
actually loaded instead of printing the score alone.

**Residual risk.** Unbounded, and uncontrolled. Nothing measured so far
constrains the variant caller's error rate, and this remains the one hazard in
the document with no mitigating control, which is why it is open action 1.

### F7. Rejected variant calls were ingested as if they had passed (H1, H6) — FIXED

`_parse_and_annotate_vcf` in `api/workers/genomic_worker.py` unpacked the VCF
FILTER column and then discarded it. Calls the variant caller had explicitly
rejected were ingested identically to passing calls, and nothing downstream could
tell the difference because the value was not retained.

Mutect2 emits `weak_evidence`, `strand_bias`, `base_qual` and `panel_of_normals`
for calls it believes are artefacts or germline. Those are precisely the calls
that must not reach a treatment recommendation. Demonstrated with a three-record
VCF: two rejected calls and one PASS call all arrived as equal mutations.

Rejected calls are now dropped, `PASS` and `.` are accepted, `include_filtered=True`
retrieves them when a caller genuinely wants them, and the FILTER value is
retained either way so the decision is inspectable.

**Residual risk.** The filter now depends on the upstream caller emitting FILTER
at all. A VCF whose every record carries `.` is accepted wholesale, and "passed
the caller's filters" is not currently distinguished from "was never filtered".

### F8. Multi-allelic sites were collapsed into one unusable variant (H2) — FIXED

A multi-allelic record describes several distinct variants. The parser stored the
ALT column verbatim, so `GGTTT,GTTTT` became a single mutation whose alt allele
matches no evidence record. Found by running the parser over the Genome in a
Bottle HG002 benchmark VCF (NIST v4.2.1, GRCh38): 46 of 8,000 real records were
affected.

Nothing upstream normalises. There is no `bcftools norm` step anywhere in
`pipeline/`. If one of the two alleles is the actionable one, it was silently
lost. Each ALT allele is now emitted as its own mutation.

**Residual risk.** Splitting ALT alleles is not left-normalisation. With no
`bcftools norm` step anywhere in `pipeline/`, an indel written differently from
the evidence record's representation still fails to match, and the size of that
class is unmeasured.

### F9. Allele fraction never reached the mutation record (H1, H3) — FIXED

The parser read no FORMAT fields, so mutations carried no VAF or depth. A 2%
cytosine-deamination artefact and a 50% clonal driver were indistinguishable
downstream.

This also made the FFPE detector inapplicable to anything this parser produced:
`detect_ffpe_artefacts` in `api/services/sample_qc.py` keys on low-VAF
enrichment, and the production ingestion path supplied no VAF for it to read. So
the control existed and was validated (`scripts/validate_ffpe_detection.py`)
while being unreachable from the path that matters. VAF is now derived from
`AF` or from `AD` allelic depths, with depth carried alongside.

Regression tests for F7, F8 and F9: `api/tests/test_vcf_ingestion_safety.py`.

**Residual risk.** VAF is only as good as the FORMAT fields present. A VCF
carrying neither `AF` nor `AD` yields no VAF, the FFPE detector then has nothing
to key on, and that state currently reads downstream like a clean sample.

### F10. Sample QC was implemented, validated, and never invoked (H1, H3) — FIXED

`api/services/sample_qc.py` implements FFPE artefact detection, tumour purity
estimation and coverage summary, with unit tests, and
`scripts/validate_ffpe_detection.py` measures its sensitivity. None of that
mattered, because **no worker or route ever called it**. A grep for
`run_sample_qc` and `detect_ffpe_artefacts` outside the tests returns only the
definitions themselves.

So a sample with a high-confidence FFPE deamination signal produced drug
recommendations exactly like a clean one, and the patient-facing report printed
"QC report not provided" as its normal state.

That message also named a function that does not exist,
`sample_qc.run_qc_pipeline()`. The real entry point is `run_sample_qc()`. Anyone
following the report's own instruction got an `AttributeError`. Corrected.

`_run_sample_qc_checkpoint` now runs QC in the genomic worker and logs at the
severity the verdict warrants, `ERROR` on FAIL. QC is advisory and never fails
the submission, because discarding a real analysis over a quality signal is the
wrong trade.

The verdict now reaches the report. `submissions.sample_qc` (migration `0011`)
persists it, `sample_qc_to_report_dict()` maps `SampleQCReport` onto the exact
keys `oncologist_report._format_qc` reads, and both report call sites in
`api/routes/results.py` pass it through. The column is nullable, so submissions
processed before this keep reading as "not assessed" rather than being
retroactively claimed to have passed: absence of a verdict and a passing verdict
must not render alike. `_format_qc({})` returns `qc_verdict="UNKNOWN"` with every
measurement `None`, which is the property the tests pin.

This is the general lesson from F9 as well: a control that is implemented,
tested and benchmarked can still be doing nothing. Validation shows a control
works; only tracing the call path shows it runs.

**Residual risk.** QC is advisory by design, so a FAIL verdict still produces
recommendations and still depends on a reader noticing the verdict. Whether it
should ever block output is the same unanswered policy question as open action
4.

### F11. Controls that were mounted but not reached (H3) — FIXED

Three instances of F10's pattern, found by asking which controls run rather than
which exist.

`/api/fhir` was absent from `_PHI_PREFIXES` in `api/middleware/audit.py`.
`DiagnosticReport` and `Observation` export a patient's full variant profile,
and neither produced a `phi_access` record or an `X-Request-Id`: the richest PHI
export in the API was the one path with no audit trail. Every existing prefix
test asserted a positive about a prefix already in the tuple, so the suite could
not see an omission. It now walks the mounted routes instead.

`api/routes/results.py` swallowed any exception from the patient summary and the
oncologist report into a bare `pass`. The response returned 200 with a null
section, which is indistinguishable from a section with nothing to say. Both now
log the traceback and name the failure in `generation_errors`. The generators
still cannot fail the request, which remains correct.

`notify_review_complete` looked its `Result` up with `db.get(Result, submission_id)`.
`Result.id` is its own UUID and `submission_id` is a separate unique FK, so the
lookup never matched and the task returned success having sent nothing. Fixed to
query on `submission_id`. Three of the five notification tasks still have no
dispatcher at all, and `notify_campaign_milestone`'s only dispatcher is itself
never called, so milestone emails cannot fire; both are recorded in the wiring
test rather than left to be rediscovered.

**Residual risk.** The route-table walk catches a prefix nobody added; it cannot
catch PHI served from a route nobody thought of as a PHI route. Three
notification tasks are still undispatched and `notify_campaign_milestone` still
cannot fire, recorded rather than fixed, so milestone email remains a known dead
path.

### F12. A replayed Stripe webhook inflated donation totals (H5) — FIXED

`_handle_succeeded` in `api/routes/webhook.py` did
`campaign.raised_usd = (campaign.raised_usd or 0) + amount_usd` with nothing
recording which events had already been applied. Stripe documents at-least-once
delivery and redelivers on any non-2xx response or timeout, so this is ordinary
traffic rather than an error path, and the total only ever moved upward.

This is H5 outside the benchmark suite: a public figure that overstates what
happened. It is also the only endpoint in the system that moves money, and it
had no test of any kind.

Every event id is now claimed in `stripe_webhook_events` (migration `0012`)
before any handler runs, and a repeat is acknowledged with `duplicate: true`
without being processed. The id is the primary key rather than a unique column
so two concurrent redeliveries resolve in the database instead of in a
check-then-act race. Claiming commits before the handler runs: if a handler then
fails the event is not retried, which is the right trade here, because a
redelivery adds money that was never paid and that error is neither visible in
nor reversible from the campaign total.

The bare `except Exception` around `construct_event` also answered every
internal parsing bug with "Invalid webhook payload", which Stripe retries
indefinitely while the real cause went unrecorded. It now logs the traceback.

**Residual risk.** Claiming before handling converts a double credit into a
possible dropped event when a handler raises. That is the right direction, but
nothing alerts on a claimed event whose handler failed, so a donation that was
paid and never recorded is currently visible only in the traceback log.

### F13. An unauthenticated endpoint disclosed Stripe account state (H5) — FIXED

`GET /api/stripe/connect/return/{pharma_id}` returned `stripe_account_id`,
`charges_enabled` and `payouts_enabled` for whatever id appeared in the path,
with no credential of any kind. Walking the ids read back the Stripe account and
payout state of every company on the platform. It also returned 404 for unknown
ids and 200 for known ones, so it confirmed which ids existed before the body
was even read.

It cannot require a token: it is the `return_url` given to
`stripe.AccountLink.create`, so Stripe redirects the pharma's browser here with
no Authorization header, and adding `_require_admin` would reject every pharma
the moment they finish KYC. The fix is to stop it answering questions. It now
returns the same shape for every id and reports only whether onboarding
finished. Everything it used to disclose remains available from
`GET /status/{pharma_id}`, which requires the admin role.

**Residual risk.** Onboarding completion is still readable without a credential
for any id a caller can guess. That is accepted: it is one boolean, and Stripe
already reveals it to the browser it redirects here. Nothing else on this route
now varies with the id.

### F14. A patient's diagnosis and variant profile were readable without a credential (H3) — FIXED

`GET /api/marketplace/drug-requests/{request_id}` took no authentication and
returned `cancer_type`, `target_gene` and `mutation_profile`, where
`mutation_profile` is up to 12 HGVS variant notations assembled by
`build_custom_discovery_brief` in `api/services/drug_discovery.py`. That is a
cancer diagnosis and a genomic profile, served to anyone who asked.

Obscurity was not protecting it either. `GET /api/marketplace/drug-requests` is
also unauthenticated and returns `drug_request_id` for every open request, so
the identifiers needed for the detail call were being published by the endpoint
immediately beside it. Walk the list, then read each record.

The route sits under `/api/marketplace`, which **is** in `_PHI_PREFIXES`, so
every one of those reads was written to the audit log as a PHI access. The
system recorded the disclosure accurately while permitting it. That is the
inverse of F11: there a control was missing, here the control was present,
working, and reporting on an access that should never have been possible. A
correct audit trail is not an access control, and this is what it looks like
when the two are confused.

Found by the sweep that section 8.1 recorded as not done, by asking which
mounted routes require no credential rather than checking that the guarded ones
are guarded. The same question that found F11.

Fixed by requiring authentication on the detail route.
`api/tests/test_marketplace_phi_disclosure.py` pins it, and generalises: the
suite now walks every route under a PHI prefix and fails on any that is
anonymous unless it is named in an exemption list with a reason. Five routes are
named there, each a company record, a donation intent, or a campaign the patient
explicitly published.

**Residual risk.** The fix is authentication, not authorisation. Any
authenticated principal can still read any drug request. Scoping it to the
owning patient plus the companies entitled to bid needs a pharma role, which the
Keycloak realm does not define, so the narrowing is recorded here rather than
guessed at.

---

## 3. What is not yet analysed

Listed explicitly so the gaps are not mistaken for absent risk.

- **No failure-mode quantification.** Nothing measures how often a
  recommendation is wrong, in either direction. F1 and F2 were found by reading,
  not by a metric that would have alerted on them.
- **No harm severity model.** Hazards above are ranked by argument, not by a
  scored likelihood-times-severity register. `REGULATORY_FRAMEWORK.md` requires
  one before clinical use.
- **No human-factors analysis.** How a clinician reads a ranked list, whether
  rank order is interpreted as confidence, and whether the disclaimers are read
  at all, are untested.
- **Custom drug discovery output.** Stage two produces molecule briefs.
  `REGULATORY_FRAMEWORK.md` section 4 defines safety gates; whether the
  implemented in-silico panel is sufficient is not assessed here.
- **LLM-generated patient summaries.** The plain-language summary path is a
  generative component whose failure modes (fabrication, unwarranted certainty)
  are not analysed.

---

## 4. Controls currently in place

Verified present, not merely intended:

- Resistance entries merged from the static table as a floor on the live path
  (`api/services/oncokb_evidence.py`), and now reachable in the worker path too.
- Resistance markers excluded from primary recommendations in the benchmark
  paths (level filtering before ranking).
- Gene symbol alias resolution so a report naming `HER2` reaches `ERBB2`
  evidence (`api/services/oncokb_evidence.py`; a sweep found 26 of 29 legacy
  symbols previously unreachable, `scripts/audit_gene_symbols.py`).
- Drug trade name to INN resolution (`scripts/audit_drug_names.py`).
- Cancer-context matching on recorded histology.
- Circularity gate on the concordance answer key
  (`scripts/detect_label_circularity.py`, exits non-zero).
- Unparseable OncoKB levels resolve to `unknown` rather than raising or being
  read as actionable (fail-safe direction).
- Evidence provenance retained and stamped onto each result
  (`get_evidence_provenance` in `api/services/oncokb_evidence.py`,
  `results.evidence_provenance`), with the degraded static-fallback path logged
  at `WARNING`.
- Sample QC verdict returned to API callers as well as to the
  rendered report (`submissions.sample_qc`, `ResultsResponse.sample_qc`), with
  "not assessed" rendered distinctly from "passed" in
  `web/components/SampleQCCard.tsx`.
- The genomic worker's QC call path is pinned by an integration test that drives
  `run_genomic_pipeline` and asserts on the persisted row
  (`api/tests/test_genomic_worker_qc_persistence.py`), so a control that stops
  being invoked fails a test rather than going quiet.
- A failed report or summary generation is named in the response
  (`ResultsResponse.generation_errors`) and logged with its traceback, rather
  than returning a null section that reads like an empty one.
- Every PHI route the app mounts is covered by the audit middleware's prefix
  list, asserted by walking the app's own route table
  (`api/tests/test_middleware_audit.py::TestEveryMountedPhiRouteIsAudited`).
- Every Celery notification task either has a dispatcher or is listed as a known
  gap with a reason (`api/tests/test_notify_worker_wiring.py`).
- Every route under a PHI prefix is asserted to require a credential, or named
  in an exemption list with the reason it is public
  (`api/tests/test_marketplace_phi_disclosure.py`).
- Generated patient text is validated before it is returned, and failing text
  falls back to the deterministic template rather than being published with a
  warning (`api/services/llm_output_guard.py`).
- A degraded evidence base is refusable by policy and alarms when sustained
  (`enforce_evidence_policy`, `require_current_evidence`).

---

## 5. Hazard traceability

Which hazard each finding belongs to, what now stands against it, and the test
that fails if that control stops running. A control with no test in the last
column is asserted, not enforced.

| Hazard | Findings | Control in place | Test that fails if it stops running |
|---|---|---|---|
| H1 resistance ignored | F1, F7, F9 | Static-table resistance floor reachable on the worker path; rejected calls dropped; VAF carried onto the mutation | `test_ai_worker_oncokb_levels.py`, `test_vcf_ingestion_safety.py` |
| H2 actionable variant missed | F2, F8 | Wire format mapped onto `OncoKBLevel`; each ALT allele emitted separately | `test_ai_worker_oncokb_levels.py`, `test_vcf_ingestion_safety.py` |
| H3 lookup failure read as a negative | F3, F10, F11, F14 | `evidence_provenance` returned with the answer; QC verdict persisted and rendered; audit coverage derived from the mounted route table; `generation_errors` names a failed section | `test_evidence_provenance.py`, `test_genomic_worker_qc_persistence.py`, `test_middleware_audit.py::TestEveryMountedPhiRouteIsAudited`, `test_marketplace_phi_disclosure.py`, `test_evidence_lookup_status.py` |
| H4 stale evidence base | F4 | Provenance stamped onto the result at production time; static fallback logged at `WARNING` | `test_evidence_provenance.py` |
| H5 overstated figures | F5, F12, F13 | Circularity gate on the answer key; webhook event ids claimed before handling; Connect return route no longer varies by id | `scripts/detect_label_circularity.py` in CI, `test_webhook_and_stripe_disclosure.py` |
| H6 wrong variant call | F6, F7 | **None for calling accuracy.** F7 removes calls the caller itself rejected, which is not the same thing. The gate's measuring instrument exists but has never been given caller output | `test_vcf_ingestion_safety.py` and `test_variant_calling_validation.py` cover the harness, not the caller |

H6 has no control. The row is here so that absence does not read as coverage by
being left out. Every control in the H3 row was added after the thing it
controls was found inert, so that row is the newest and the least exercised.

Coverage here means the control runs, not that it is sufficient. Nothing in this
table measures how often a hazard is actually realised; that is open actions 1
and 2.

---

## 6. Open actions, in priority order

| # | Action | Hazard | Blocking clinical use? |
|---|---|---|---|
| 1 | Run `scripts/validate_variant_calling.py` against HG002 calls from `pipeline/main.nf`. Harness and truth set ready; needs a host with the toolchain | H6 | Yes |
| 2 | Biomarker-driven key measured (NCI-MATCH, `BENCHMARK_NCI_MATCH.md`). The benchmark calls only Tier 1, so neither its headline nor the 7.1% independent split measures generalisation. **Next: make `benchmark_nci_match.py` invoke both tiers**, then requantify. 6 of 13 misses are already Tier 2 reachable; 4 are real coverage gaps | H5 | Partly |
| 3 | ~~Carry lookup-failure state per *variant*~~ **Done 2026-08-19**, migration `0014`, `mutations.evidence_lookup_status` | H3 | Closed |
| 4 | ~~Decide whether a degraded evidence base should block output~~ **Done 2026-08-19**, `require_current_evidence` policy plus a sustained-fallback alarm | H4 | Closed |
| 5 | ~~Formal risk register with likelihood and severity scoring~~ **Done 2026-08-19**, [RISK_REGISTER.md](RISK_REGISTER.md) | all | Closed |
| 6 | Human-factors review of how the ranked list is read | all | Yes |
| 7 | ~~Analyse LLM summary failure modes~~ **Done 2026-08-19**, `services/llm_output_guard.py` with fallback to the template path | H5 | Closed |
| 8 | ~~Restore the indexes `a8bf7eb4833c` dropped~~ **17 of 19 restored 2026-08-19**, migration `0015`; two were unrestorable and the reasons are in the migration. VARCHAR bounding still open | — | No |

---

## 7. Note on benchmark-derived risk

The circular concordance benchmark (F5) is the clearest instance of H5 in this
project's history: a 100% figure reached the preprint abstract, and no test
could have caught it because the defect was in how the question was posed, not
in the code that answered it. The lesson generalises. A benchmark that cannot
fail is a risk control that does not exist, and it is more dangerous than no
benchmark because it displaces one.

Any future validation result should be accompanied by an answer to "what result
would have falsified this?" before the number is quoted.

---

## 8. Security, privacy and vendor risk

This section used to list four topic areas rather than four risks, which is why
F11, F12 and F13 were all found inside it after it had been written. It now
names the hazard in each area, on the same terms as sections 1 and 2.

### 8.1 Hazards

| # | Hazard | Status |
|---|---|---|
| S1 | A PHI route is served without an audit record, so an access cannot later be shown to have happened or not happened | Controlled, see 8.2. Was live until F11 |
| S2 | An endpoint answers a question it should not, or answers differently for a known and an unknown id | Swept 2026-08-19. F13 and F14 fixed; every PHI-prefixed route is now asserted authenticated or exempted with a reason (`test_marketplace_phi_disclosure.py`). Authorisation within an authenticated session is still coarse |
| S3 | A money-moving endpoint applies the same event twice | Controlled by claim-before-handle, F12 |
| S4 | Schema or migration drift silently breaks the audit trail's own storage | Controlled in CI, see 8.2 |
| S5 | Vendor dependency failure | For OncoKB this is **not** primarily an availability risk. It is the wrong-answer risk in F4, and it is the reason that finding is rated above ordinary uptime concerns |
| S6 | A scanner exists but does not run before the code it would have caught is merged | Was live until the `pull_request` trigger below; partially controlled |

The authentication sweep is done. Role checks *within* an authenticated
session, and per-route rate limits, remain unswept and stay under S2.

### 8.2 Controls, verified present

- Structured PHI access logging middleware, with prefix coverage derived from
  the app's own mounted route table rather than a hand-kept list
  (`_PHI_PREFIXES` in `api/middleware/audit.py`).
- Keycloak JWT auth and role extraction.
- A Redis-backed rate limiter. It exists; which routes actually apply it is the
  unswept half of S2.
- Migration drift gating in CI: `alembic check`, plus a revision-graph gate in
  `scripts/check_migration_chain.py`.
- Every Stripe event id claimed in `stripe_webhook_events` before any handler
  runs (migration `0012`).

### 8.3 Scanning

Scanning deserves a more exact statement than "in CI", because the earlier
wording claimed more than ran. Dependency, SAST, DAST and image scanning all
exist in `.github/workflows/security.yml`, but until now that workflow had no
`pull_request` trigger, so none of it ran before a merge: findings surfaced after
the change was already on `main`, or up to a week later on the weekly cron. The
fast jobs now run on pull requests. What each one can actually do:

| Scan | Runs on PR | Can fail the build |
|---|---|---|
| pip-audit (Python deps) | yes | yes |
| npm audit (frontend deps) | yes | only at `critical`; 6 HIGH advisories in a transitive `postcss` are unfixable without a breaking Next.js major |
| Bandit (Python SAST) | yes | no, reports to the Security tab |
| Semgrep (SAST) | yes | no, reports to the Security tab |
| CodeQL (SAST) | yes | yes |
| ZAP (DAST) | no, push/cron only | no, report only |
| Trivy (image) | no, push/cron only | yes, on `main` |

**Residual risk.** ZAP and Trivy still run only after merge, so a DAST or image
finding is discovered on `main`. Bandit and Semgrep report without blocking, so
a new finding from either lands unless someone reads the Security tab. The
`postcss` advisories are accepted and unfixable without a breaking Next.js
major, which means the npm audit threshold is set by what is tolerable rather
than by what is safe.

**Open.** Formal risk register with per-control scoring; audit log retention and
immutability verification in the deployment environment; a sweep of route-level
role checks and rate limits for S2; promoting Bandit and Semgrep to blocking
once their current findings are triaged.

---

## 9. Review cadence

**Owner:** Aashish Kharel, repository maintainer. Single-maintainer project, so
the cadence below is self-enforced and that is itself a weakness worth naming:
nothing external triggers a review if one is missed.

**Last reviewed:** 2026-08-19, at which point every file-and-symbol citation in
this document was re-checked against the tree and one drifted line-range
citation was found and replaced. That check is part of the review, not a
one-off.

- Baseline: quarterly. Next due 2026-11-19.
- Triggered: after any change to the evidence table, the ranking function, the
  variant calling pipeline, or any benchmark used to support a performance
  claim.
- Every finding above must be re-verified before any statement of clinical
  readiness.
