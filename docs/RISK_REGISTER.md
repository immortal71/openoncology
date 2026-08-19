# Risk register

Companion to [risk_analysis.md](risk_analysis.md), which argues each hazard from
code. This scores them. Open action 5.

**Status.** Research use only. No entry below is closed for clinical use.

---

## How probability is handled

[risk_analysis.md](risk_analysis.md) states that a hazard which is real but
unquantified is recorded as unquantified rather than given an invented
likelihood. A register that assigned probabilities anyway would contradict the
document it accompanies, and inventing a "1 in 10,000" for a defect nobody has
measured is worse than leaving the cell empty, because it looks like evidence.

So this register follows the convention ISO 14971 provides for exactly this
case: **where the probability of a software failure cannot be estimated from
data, it is not estimated. The hazardous situation is assumed to occur, and the
risk is evaluated on severity alone.** That is deliberately conservative, and it
has a useful property: an entry can only be de-escalated by producing a
measurement, never by argument.

Two columns therefore appear where a conventional register would have one
probability:

- **P** — probability of the hazardous situation. `ASSUMED` until measured.
- **Evidence needed** — the specific measurement that would replace `ASSUMED`
  with a number. If this column is empty, the entry is not actionable and that
  is a defect in the entry.

### Severity scale

| S | Label | Meaning for this system |
|---|---|---|
| 5 | Catastrophic | Contributes to a treatment decision that causes death or irreversible harm |
| 4 | Critical | Effective therapy is delayed or withheld; harm is serious but recoverable |
| 3 | Serious | Wrong information reaches a clinician, is caught, and costs time and trust |
| 2 | Minor | Degraded output, no plausible path to a treatment decision |
| 1 | Negligible | Cosmetic or internal only |

### Risk evaluation

With P assumed, risk class follows severity: **S5 and S4 are unacceptable for
clinical use**, S3 is unacceptable without a mitigating control, S2 and below
are tolerable with monitoring. Every S4 and S5 entry below is therefore open by
construction, which is the correct reading of a system whose validation gates
are unmet.

---

## Register

| ID | Hazard | Cause | S | P | Controls in place | Residual | Evidence needed |
|---|---|---|---|---|---|---|---|
| R1 | Drug recommended that the variant confers resistance to | Resistance evidence not reaching the ranker (F1) | 5 | ASSUMED | Static-table resistance floor reachable on both paths; enum-to-enum comparison; `test_ai_worker_oncokb_levels.py` | Open | Resistance-marker coverage audit of the static table; error rate against a biomarker-driven key (open action 2) |
| R2 | Actionable variant present and never surfaced | Wire-format/enum mismatch (F2); multi-allelic collapse (F8) | 5 | ASSUMED | Wire format mapped onto `OncoKBLevel`; per-ALT emission; `test_vcf_ingestion_safety.py` | Open | Open action 2; left-alignment coverage for indel representation |
| R3 | Lookup failure read as "nothing actionable" | Evidence source unreachable, no per-variant record (F3) | 4 | ASSUMED | `mutations.evidence_lookup_status` (0014); provenance on the result (0013); report prints a warning per unanswered gene | Reduced, open | Rate of lookup failure in a real deployment; currently unobserved because no deployment configures a token |
| R4 | Recommendation from an evidence base of unknown currency | OncoKB dump unreachable, static fallback (F4) | 4 | **OBSERVED** | Provenance stamped at production time; `require_current_evidence` policy; sustained-fallback alarm, which fired on all 33 resolutions of a real benchmark run on 2026-08-19 | Reduced, open | How much actionability changes across the 7-day cache window |
| R5 | Performance claim overstates what was measured | Circular benchmark (F5); replayed webhook (F12); a benchmark figure carried by the subset the engine already held (2026-08-19) | 4 | **OBSERVED** | Circularity gate in CI; webhook event ids claimed before handling; harness records `satisfies_regulatory_gate_3_1`; `audit_nci_match_independence.py` splits contained from independent arms | Reduced, open | A larger independent arm set. With both tiers the split is 70.6% contained against 20.0% independent on 15 arms, which is an observation rather than an estimate |
| R6 | Variant call is wrong and everything downstream is applied to it | Unvalidated calling pipeline (F6) | 5 | ASSUMED | **None for calling accuracy.** F7 drops caller-rejected calls, which is a different thing | **Open, uncontrolled** | Open action 1: run `scripts/validate_variant_calling.py` on this pipeline's HG002 output |
| R7 | Caller-rejected artefact drives a recommendation | FILTER discarded at ingestion (F7) | 5 | ASSUMED | Rejected calls dropped; FILTER retained; `include_filtered` opt-in | Reduced | Rate of rejected calls in real submissions; behaviour on VCFs with no FILTER column populated |
| R8 | Low-VAF artefact treated as a clonal driver | No VAF carried through (F9); QC never invoked (F10) | 4 | ASSUMED | VAF and depth from `AF`/`AD`; QC runs in the genomic worker and persists; `test_genomic_worker_qc_persistence.py` | Reduced | FFPE detector sensitivity on real paired tissue, not spike-in simulation |
| R9 | Generated patient text fabricates a drug, a prognosis, or a certainty | LLM summary path (open action 7) | 4 | ASSUMED | `llm_output_guard.validate_patient_summary`; failing text falls back to the deterministic template; path deprecated in favour of template-only summaries | Reduced | Rate of guard rejections against real generations; the guard catches known phrasings only |
| R10 | Clinician misreads rank order as confidence | No human-factors work (open action 6) | 4 | ASSUMED | Disclaimers; tier gap explanation in the report | **Open, uncontrolled** | Open action 6: observe oncologists reading real reports |
| R11 | PHI access occurs with no audit record | Route not covered by audit middleware (F11) | 3 | **OBSERVED** | Prefix coverage derived from the mounted route table; `TestEveryMountedPhiRouteIsAudited` | Reduced | Audit-log retention and immutability verification in a deployed environment |
| R12 | Unauthenticated caller reads another party's account state | Connect return route disclosed by id (F13) | 3 | **OBSERVED** | Route returns the same shape for every id | Reduced, partial | Role checks within an authenticated session; per-route rate limits |
| R15 | A tied set of candidates is presented to a clinician as a ranked list, so rank order carries information it does not have | Absent evidence sources have their weight redistributed, so equal-evidence candidates score identically and the tie breaks alphabetically (F16) | 4 | **OBSERVED** | Ordering is deterministic and reproducible; behaviour pinned by `test_ranking_ties.py` | **Open** | What should break a clinical tie: line of therapy, toxicity, route, cost. Belongs with open action 6 |
| R13 | Donation total overstated by replayed webhook | At-least-once delivery, no idempotency (F12) | 2 | **OBSERVED** | Event ids claimed in `stripe_webhook_events` before any handler runs | Closed for this cause | Alerting on a claimed event whose handler raised |
| R14 | Patient diagnosis and variant profile readable with no credential | Drug-request detail route unauthenticated while the listing published every id (F14) | 5 | **OBSERVED** | Authentication required; every PHI-prefixed route asserted authenticated or exempted with a reason | Reduced, open | A pharma role, so the record can be scoped to the owner and entitled bidders rather than to any logged-in principal |

**OBSERVED** means the hazardous situation has actually occurred in this
repository's history, not that its rate is known. It still has no probability.

---

## What this register says overall

Five entries are S5: R1, R2, R6, R7 and R14. Of those, R6 has no control of any
kind, and it is the one every other entry is conditioned on: a wrong variant
call makes R1, R2 and R7 irrelevant, because the reasoning is correct and
applied to something the patient does not have.

R14 is the only S5 that is a privacy failure rather than a clinical one, and the
only one found by asking which controls were absent rather than by reading the
code that implements them.

Two entries are open and uncontrolled: **R6** and **R10**. One is a measurement
nobody has run, the other is a study nobody has done. Neither is an engineering
defect, which is the same conclusion
[ROADMAP_TO_CLINICAL_USE.md](ROADMAP_TO_CLINICAL_USE.md) reaches from the other
direction.

No entry can be de-escalated by writing more code. Every "Evidence needed" cell
names a measurement or a study.

---

## Review

Owner: Aashish Kharel, repository maintainer. Reviewed with
[risk_analysis.md](risk_analysis.md) section 9, quarterly, next due 2026-11-19,
and on any change to the ranking function, the evidence table, or the variant
calling pipeline.

Created 2026-08-19.
