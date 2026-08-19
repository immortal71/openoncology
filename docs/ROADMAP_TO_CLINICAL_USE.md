# Roadmap to clinical use

**Goal.** OpenOncology used by oncologists to inform real treatment decisions,
and by patients through their clinician.

**Where this stands on 2026-08-19.** Research use only. Every clinical
validation gate in [REGULATORY_FRAMEWORK.md](REGULATORY_FRAMEWORK.md) section 3
is unmet. The honest summary is that engineering is no longer the binding
constraint on most of what remains: studies, an institutional partner, and a
regulatory submission are. This document separates what can be finished by
writing code from what cannot, so effort goes where it still moves something.

Three horizons follow. Work in an earlier horizon is a prerequisite for the
next, and nothing in horizon 3 starts without a partner institution.

---

## Horizon 1 — Immediate: finish what code alone can finish

Everything here is unblocked, needs no external party, and either closes a
listed open action or removes a hazard in
[risk_analysis.md](risk_analysis.md).

| # | Item | Hazard | State |
|---|---|---|---|
| 1.1 | Variant-calling validation harness against GIAB HG002 | H6 | Done, `scripts/validate_variant_calling.py` |
| 1.2 | Per-variant evidence lookup state, so one failed gene does not read as four negatives | H3 | Done, migration `0014` |
| 1.3 | Reference measurement of a stock GATK4 pipeline through the harness | H6 | Done, see below |
| 1.4 | Policy and enforcement for a degraded evidence base | H4 | Done, `require_current_evidence` |
| 1.5 | Formal risk register with likelihood and severity scoring | all | Done, [RISK_REGISTER.md](RISK_REGISTER.md) |
| 1.6 | LLM patient-summary failure-mode analysis and guardrails | H5 | Done, `services/llm_output_guard.py` |
| 1.7 | Restore the dropped indexes; bound the unbounded VARCHAR columns | — | Indexes done (17 of 19, migration `0015`). VARCHAR open |
| 1.8 | Route-level authorisation sweep | S2 | Done, and it found F14 |
| 1.9 | Merge the two `ai` packages so the repurposing tier runs outside the container | H2 | Done, F15 |
| 1.10 | Make the benchmark measure the pool production actually uses | H5 | In progress |
| 1.11 | Algorithm version locking and change control | — | Required by section 2.3 |

**On 1.7's VARCHAR half.** The open action says 11 unbounded VARCHAR columns.
There are 21, and 19 of them are UUID primary keys carrying
`str(uuid.uuid4())`, so bounding them means altering a primary key type on
roughly fifteen tables and every foreign key pointing at one. The two that are
not primary keys, `drug_requests.accepted_bid_id` and
`deletion_requests.patient_id`, both hold UUID references to those same keys, so
narrowing them alone would leave each side of a foreign key a different width.
This is a storage and validation improvement with no safety consequence, and the
migration risk is concentrated on every table at once, so it is deliberately
still open rather than done in passing. Same pattern as the index count: the
number in the open action was not right either.

**What 1.3 measured, and what it did not.** A published NIST HG002 call set
made with GATK HaplotypeCaller 4.1.4.1 under GATK Best Practices, scored on
GRCh38 chr20 inside the NIST high-confidence regions: 95.82% sensitivity and
98.87% PPV overall; 95.69% / 99.98% for SNVs; 96.60% / 92.81% for indels. That
is a real, discriminating measurement, and it is **not** this repository's
pipeline. It is recorded as `satisfies_regulatory_gate_3_1: false`.

It carries one finding worth acting on: a stock GATK4 pipeline measured this
way lands near 96% sensitivity, well under the 99% the gate demands. Either the
gate expects better than stock tuning, or the comparison must become
haplotype-aware (hap.py, rtg vcfeval) rather than allele-identity, or the
target itself needs revisiting against what the field actually achieves. That
question is answerable before any partner exists.

---

## Horizon 2 — Medium: what needs data, but not yet a clinic

Blocked on obtaining data rather than on running a study. Public sources
already used elsewhere in this repository (cBioPortal, GDC) make some of it
reachable without an institutional agreement.

| # | Item | Blocking clinical use? |
|---|---|---|
| 2.1 | Run the harness on this repository's own pipeline output for HG002 | Yes, open action 1 |
| 2.2 | Non-circular concordance measurement against a biomarker-driven answer key | Yes, open action 2 |
| 2.3 | Retrospective concordance against real tumour-board decisions, n >= 100 | Yes |
| 2.4 | Benchmark against commercial platforms, section 3.3 | Yes |
| 2.5 | Human-factors study of how a ranked list is read | Yes, open action 6 |

2.1 needs a host with `bwa-mem2`, `gatk`, `samtools` and a GRCh38 reference.
Nothing about it is unsolved; it needs a machine, and it is the single cheapest
remaining item on the critical path.

2.3 is the first item that genuinely requires an institution. Everything before
it can be done with public data and rented compute.

---

## Horizon 3 — Long: what needs institutions and regulators

None of this is reachable by writing code, and listing it here is a way of not
pretending otherwise.

| # | Item | Typical duration |
|---|---|---|
| 3.1 | Partner institution and data-use agreement | Months, unpredictable |
| 3.2 | IRB-approved prospective pilot, n >= 50 | 1 to 2 years |
| 3.3 | Multi-site clinical utility study, n >= 500 | Multi-year, needs funding |
| 3.4 | ISO 13485 quality system, locked algorithm, change-control SOP | Runs in parallel |
| 3.5 | FDA De Novo or EU IVD-R Class C submission | Review alone is months |

A patient-facing product without a clinician in the loop is a companion
diagnostic in the hardest regulatory posture available, section 2.3. The
reachable form of "used by patients" is a report an oncologist hands to their
patient, and the roadmap is built for that.

---

## What would falsify this plan

Kept here because [risk_analysis.md](risk_analysis.md) section 7 requires any
claim to name what would disprove it.

- If horizon 1 completes and no partner institution is interested, the binding
  constraint was never engineering readiness, and horizon 2 onward does not
  begin. That is the most likely way this stalls.
- If the reference measurement in 1.3 reflects what the pipeline itself
  achieves, the 99% sensitivity gate is not reachable with a stock GATK4
  configuration and the pipeline needs work that is not yet scoped.
- If the concordance measurement in 2.2 comes back near chance once the
  circularity is gone, the ranking approach is wrong rather than
  under-validated, and the project is further from clinical use than this
  document assumes.

---

## Review

Owner: Aashish Kharel, repository maintainer. Reviewed alongside
[risk_analysis.md](risk_analysis.md) section 9, quarterly, next due 2026-11-19.
