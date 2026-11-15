# Clinical tool conventions: what the Results workspace should feel familiar to

**Date:** 2026-11-15
**Scope:** the inside of tools (variant review, reports, evidence lookup), not marketing pages.
**Rule:** match the field's conventions (terminology, badge meaning, layout patterns) so clinicians don't relearn anything. Don't copy another product's code, logos, artwork or branded visuals. Familiar, not identical.

## Who uses what

| User | Typical tools | The insight they look for first |
|---|---|---|
| Molecular pathologist | Variant interpretation platforms, ClinVar, IGV | Is the call real (VAF, depth, reads), and what tier is it? |
| Anatomic pathologist | Whole-slide viewers with AI overlays | Where is the tumor, and how much (tumor %, cell counts, IHC scores)? |
| Oncologist | Genomic reports (FMI, Tempus, Caris style), OncoKB, CIViC | Which therapies, in which context, on what level of evidence? |
| Tumor board | Case-summary tools | One screen per case: timeline, key findings, decision |
| Researcher | cBioPortal, ProteinPaint | How common is this, and what co-occurs? (OncoPrint, lollipop, survival) |

## Conventions worth matching

1. **Therapies grouped by clinical context.** Reports separate drugs approved for this biomarker from drugs approved elsewhere, from investigational options and from resistance. A single flat ranked list hides that difference.
2. **Resistance is its own labelled section.** Drugs a variant makes less likely to work are listed, not dropped, with a "resistance" label.
3. **Evidence level as a named badge.** OncoKB Level 1, 2, 3A, 3B, 4, R1, R2; AMP/ASCO/CAP Tier I–IV. Always text, never colour alone, and the same treatment on every screen.
4. **Detail in a side drawer.** Clicking a variant or drug opens a panel with gene, HGVS (c. and p.), protein position and domain, VAF and depth, population frequency, ClinVar classification and review stars, and COSMIC count. The table stays in place.
5. **Absent data is stated.** "Not reported" rather than an empty cell, so a missing VAF isn't mistaken for zero.
6. **Identifiers in monospace.** HGVS, coordinates, PMIDs, ChEMBL IDs.
7. **Provenance on each number.** Source and version next to, or one hover from, each value.
8. **Uncertainty is visible.** Review stars, confidence bands, a fenced-off VUS section, near-tie notes.
9. **Tables before cards.** Sticky headers, sortable columns, row expansion.
10. **Almost no motion.** Speed and density beat polish.
11. **Review and sign-off state with history.** Draft, reviewed, signed, and who did what.

## How OpenOncology maps to this

| Convention | Data available today | Status |
|---|---|---|
| Therapies by context | `drug_tier` from `classify_drug_tier()` (`fda_approved`, `repurposed`, `investigational_late`, `investigational_early`, `preclinical`, `resistance_mechanism`) | Built on `/lab/results`: grouped list, global rank kept |
| Resistance section | `resistance_mechanism` tier | Shown when present; the demo case has none |
| Variant drawer | `gene`, `hgvs`, `classification`, `oncokb_level`, `is_targetable`; protein length and domains from `lib/protein.ts` | Built on `/lab/results`. VAF, depth, ClinVar review status and COSMIC count are not in the results payload, so they read "Not reported" |
| Evidence items per drug | Only source names today | Needs per-source evidence (level, PMID) from the API |
| Sign-off history | `oncologist_reviewed` boolean only | Needs reviewer, timestamp and history from the API |
| OncoPrint, survival | Cohort endpoints exist (`getOncoprint` and others) | Out of scope for a single-patient result |

## Group labels (wording follows the backend's own tier definitions)

| `drug_tier` | Group heading | Note |
|---|---|---|
| `fda_approved` | OncoKB Level 1–2 (standard care) | Approval status as reported on each row; the backend also files Level 1–2 drugs with unknown approval here (OO-35) |
| `repurposed` | Approved drugs, weaker or off-label evidence | Reported as approved, without Level 1–2 evidence for this variant |
| `investigational_late` | Investigational, phase 3 | |
| `investigational_early` | Investigational, phase 1–2 | |
| `preclinical` | Preclinical only | No human trial data |
| `resistance_mechanism` | Resistance (OncoKB R1–R2) | Listed for awareness, not an actionable option |
| missing | Unclassified | |

## Review findings applied (2026-11-15)

- Pathogenicity is labelled as an AlphaMissense prediction, shown only when a score exists, using the model's own class names (OO-36).
- Evidence level shows whether OncoKB was checked, using `evidence_lookup_status`: level with source, checked with no level, not checked, lookup failed, not recorded.
- Grouped rows hide the redundant tier pill and show the approval status on the row instead.
- Backend gaps logged: OO-35 (tier logic), OO-36 (AlphaMissense classes), OO-37 (VAF, depth, ClinVar and COSMIC IDs, and the variant behind each drug).
