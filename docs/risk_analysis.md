# Risk Analysis

**Scope of this document.** OpenOncology's output is a ranked list of cancer
drugs for a specific patient's variants. The dominant hazard is therefore not
downtime or data loss, it is a **wrong or absent recommendation that a reader
believes**. This document covers that hazard class. Infrastructure, PHI and
vendor risk are in [Security and privacy risk](#7-security-privacy-and-vendor-risk)
at the end, and in [HIPAA_COMPLIANCE.md](HIPAA_COMPLIANCE.md).

**Status.** Research use only. Every clinical validation gate in
[REGULATORY_FRAMEWORK.md](REGULATORY_FRAMEWORK.md) section 3 is currently
unmet, so this analysis describes hazards in a system that must not be used to
inform treatment. It is written now, before deployment, because several of the
findings below were live defects discovered by writing it.

**Method.** Every finding is traced to code or to a measured result in this
repository, and cited by file and line. Nothing here is asserted from clinical
doctrine. Where a hazard is real but unquantified, it is listed as unquantified
rather than given an invented likelihood.

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

H5 is not hypothetical for this project. See section 6.

---

## 2. Findings, verified in code

### F1. Resistance evidence never reached the ranker (H1) — FIXED

`api/workers/ai_worker.py` built a `resistance_context` for `rank_candidates`
by testing `top_mutation.oncokb_level.value in ("LEVEL_R1", "LEVEL_R2")`. The
`OncoKBLevel` enum in `api/models/mutation.py:20-28` stores `"R1"` and `"R2"`,
not `"LEVEL_R1"`. The branch could not be taken. `rank_candidates` was called
with `resistance_context=None` on every run, so a variant conferring resistance
never demoted the drug it confers resistance to.

Compounding it, `_query_oncokb` read only `highestSensitiveLevel` from the
OncoKB response and discarded `highestResistanceLevel`, so a resistance-only
annotation arrived as `unknown`. `api/services/oncokb.py:48` reads both fields
correctly; the worker's own inline client did not.

`api/services/oncokb_evidence.py:16-19` states the design intent this violated:
*"Afatinib is LEVEL_R1 for EGFR T790M, this must be surfaced even if the live
API is unavailable. The table's resistance entries act as a safety floor, never
a ceiling."* The floor existed in one code path and not in the one the worker
used.

Fixed by mapping the wire format onto the enum, comparing enum to enum, and
carrying the resistance level separately from the stored level so a variant that
is sensitive for one drug and resistant to another keeps both.
Regression tests: `api/tests/test_ai_worker_oncokb_levels.py`.

### F2. No variant was ever marked targetable on the OncoKB path (H2) — FIXED

Same root cause. `_query_oncokb` returned the wire string `"LEVEL_1"`, which was
assigned to `Mutation.oncokb_level` and then tested against enum members. The
comparison was always False, so `is_targetable` was never set and
`targetable_mutations` stayed empty, which skips the entire drug repurposing
step that depends on it.

`OncoKBLevel("LEVEL_1")` raises `ValueError`, so the assignment was also invalid
against the `SAEnum` column at `api/models/mutation.py:84-86`.

**Why this was invisible:** `_query_oncokb` returns `None` immediately when no
OncoKB token is configured (`api/workers/ai_worker.py`, token check), which is
the default. The defect only activates once a deployment configures a real
token, which is precisely when the evidence starts being relied on. Tests passed
throughout because no test exercised `_query_oncokb` or `resistance_context`.

### F3. A failed evidence lookup is indistinguishable from no evidence (H3) — PARTIALLY FIXED

When `_query_oncokb` returns `None` because the token is missing, the network
failed, or the API rate limited, the mutation is skipped and the report is
assembled without it. Nothing in the output distinguishes *"this variant has no
actionable evidence"* from *"we could not determine whether it does"*. These are
clinically opposite statements.

Now logged explicitly with the affected genes and the warning that absence of
evidence is not established. **Still open:** the distinction is not carried into
the API response or the report a reader sees. That requires a schema field and
a UI change, and `web/` is out of scope for this change.

### F4. Evidence-base provenance is not retained or surfaced (H4) — OPEN

`api/services/oncokb_evidence.py:1494-1513` resolves the actionability table
through one of three paths and records which one only as a log line:

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

**Recommended fix:** retain the bootstrap path and cache timestamp as module
state, return them in the evidence metadata, and propagate to the API response
so a report can state which evidence snapshot produced it.

### F5. Concordance benchmark was circular (H5) — FIXED

`scripts/build_concordance_labels.py` derived each patient's biomarker from the
drug they received, guaranteeing agreement. Detailed in
[ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md](ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md).
Fixed in PR #93; `scripts/detect_label_circularity.py` gates against
reintroduction. The 100% figure is retracted.

### F6. Variant calling is unvalidated (H6) — OPEN

Every recommendation is conditioned on the variant call being correct, and no
accuracy measurement exists. `REGULATORY_FRAMEWORK.md` section 3.1 sets the
target at sensitivity ≥ 99% and PPV ≥ 95% against orthogonal WGS, status
"Not completed". Until this is measured, the error rate of the entire pipeline
is unbounded, because no amount of correct downstream reasoning survives a wrong
input variant.

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

### F8. Multi-allelic sites were collapsed into one unusable variant (H2) — FIXED

A multi-allelic record describes several distinct variants. The parser stored the
ALT column verbatim, so `GGTTT,GTTTT` became a single mutation whose alt allele
matches no evidence record. Found by running the parser over the Genome in a
Bottle HG002 benchmark VCF (NIST v4.2.1, GRCh38): 46 of 8,000 real records were
affected.

Nothing upstream normalises. There is no `bcftools norm` step anywhere in
`pipeline/`. If one of the two alleles is the actionable one, it was silently
lost. Each ALT allele is now emitted as its own mutation.

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
- Sample QC verdict returned to API callers as well as to the rendered report
  (`submissions.sample_qc`, `ResultsResponse.sample_qc`), with "not assessed"
  rendered distinctly from "passed" in `web/components/SampleQCCard.tsx`.
- The genomic worker's QC call path is pinned by an integration test that drives
  `run_genomic_pipeline` and asserts on the persisted row
  (`api/tests/test_genomic_worker_qc_persistence.py`), so a control that stops
  being invoked fails a test rather than going quiet.

---

## 5. Open actions, in priority order

| # | Action | Hazard | Blocking clinical use? |
|---|---|---|---|
| 1 | Measure variant calling accuracy against a public truth set | H6 | Yes |
| 2 | Surface evidence provenance and snapshot age to the caller (F4) | H4 | Yes |
| 3 | Carry lookup-failure state into the API response and report (F3) | H3 | Yes |
| 4 | Quantify recommendation error rate against a biomarker-driven answer key | H5 | Yes |
| 5 | Formal risk register with likelihood and severity scoring | all | Yes |
| 6 | Human-factors review of how the ranked list is read | all | Yes |
| 7 | Analyse LLM summary failure modes | H5 | Yes |

---

## 6. Note on benchmark-derived risk

The circular concordance benchmark (F5) is the clearest instance of H5 in this
project's history: a 100% figure reached the preprint abstract, and no test
could have caught it because the defect was in how the question was posed, not
in the code that answered it. The lesson generalises. A benchmark that cannot
fail is a risk control that does not exist, and it is more dangerous than no
benchmark because it displaces one.

Any future validation result should be accompanied by an answer to "what result
would have falsified this?" before the number is quoted.

---

## 7. Security, privacy and vendor risk

- API authentication and authorization boundaries
- PHI data flows (upload, storage, access, deletion)
- Third-party integrations (Stripe, Keycloak, Resend, external genomic sources)
- Infrastructure controls (networking, logging, backups, disaster recovery)

Known risks: schema and version drift breaking auditability; missing route-level
rate limits and role checks; external dependency failure. Note that for OncoKB
specifically, dependency failure is **not** primarily an availability risk, it
is the wrong-answer risk described in F4.

Mitigations in place: structured PHI access logging middleware; Keycloak JWT
auth and role extraction; Redis-backed rate limiter infrastructure; dependency,
SAST, DAST and image scanning in CI.

Open: formal risk register with per-control scoring; audit log retention and
immutability verification in the deployment environment; migration drift checks
in CI.

---

## 8. Review cadence

- Baseline: quarterly.
- Triggered: after any change to the evidence table, the ranking function, the
  variant calling pipeline, or any benchmark used to support a performance
  claim.
- Every finding above must be re-verified before any statement of clinical
  readiness.
