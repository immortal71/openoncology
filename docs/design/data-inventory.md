# Frontend data inventory

What the web app actually receives, so redesigned screens only show fields that exist. Source: `web/lib/api.ts` (typed client) and `web/lib/demo-data.ts` (demo case), read on 2026-11-08.

## What the product does

A VCF goes in. A ranked list of approved drugs, repurposing candidates, or a custom-discovery brief comes out. Oncologist review is required before any treatment decision.

## Submission (dashboard list)

`GET /api/results/dashboard/all`

| Field | Type | Example |
|---|---|---|
| `submission_id` | string | `demo-nsclc-kras-g12c` |
| `cancer_type` | string | Non-Small Cell Lung Cancer |
| `status` | string | see "Status values" below |
| `submitted_at` | ISO string | |
| `completed_at` | ISO string or null | |

## Result

`GET /api/results/{submissionId}`

| Field | Type | Notes |
|---|---|---|
| `submission_id`, `status`, `cancer_type` | string | |
| `has_targetable_mutation` | boolean | |
| `target_gene` | string or null | e.g. KRAS |
| `summary` | string or null | technical one-liner |
| `plain_language_summary` | string or null | contains "Oncologist review is required…" in the demo |
| `patient_summary` | object or null | `explanation`; `top_drugs[]` (`drug_name`, `approval_status`, `patient_note`); `what_next[]` |
| `cbioportal_data` | array or null | `study_id`, `cancer_type`, `mutation_count` |
| `cosmic_sample_count` | string or null | |
| `oncologist_reviewed` | boolean | not in the demo object |
| `oncologist_notes` | string or null | not in the demo object |
| `custom_drug_possible` | boolean | not in the demo object |
| `custom_drug_reason` | string | not in the demo object |
| `mutations` | `Record<string, unknown>[]` | **loosely typed.** The demo shape is `gene`, `hgvs`, `classification`, `oncokb_level`, `is_targetable` |
| `result_id` | string or null | |

## Repurposing candidates (the ranked drug list)

`GET /api/repurposing/{resultId}`. Top level: `target_gene`, `has_targetable_mutation`, `message?`, `decision_path?`, `candidates[]`.

| Candidate field | Type | Demo example |
|---|---|---|
| `drug_name` | string | Sotorasib |
| `chembl_id` | string | CHEMBL4523582 |
| `approval_status` | string | FDA Approved |
| `mechanism` | string | Covalent KRAS G12C inhibitor… |
| `binding_score` | number or null | |
| `opentargets_score` | number or null | 0.9 |
| `rank_score` | number or null | 0.9827 |
| `evidence_sources` | string[] | OncoKB, OpenTargets, DiffDock, ClinicalPhase |
| `matched_terms` | string[] | KRAS G12C, NSCLC, AMG-510 |
| `drug_tier` | string? | `fda_approved`, `repurposed` |
| `disclaimer` | string? | |

## Other result-related endpoints

- **Clinical trials**: `getClinicalTrials`
- **Immunotherapy profile**: `getImmunotherapyProfile`
- **Mutational signature**: `getMutationalSignature`
- **Combination therapy**: `getCombinationTherapy`
- **Discovery brief**: `getDiscoveryBrief`, `getCustomDrugReport`. Fields: `lead_compounds[]` with binding, priority, exposure, feasibility and toxicity scores; `de_novo_candidates[]` with their own disclaimer; `scaffold_summary`; `next_steps`; `docking_summary`
- **Oncologist report**: `getOncologistReportPdf` (binary PDF)
- **Nearby pharmacies**: `getNearbyPharmacies`
- **Cohort and gene data**: `getStudies`, `getStudyDetail`, `getCohortMutations`, `getCrossStudyFrequency`, `getOncoprint`, `getGeneSummary`
- **Marketplace**: `createDrugRequest`, `getDrugRequests`, `listDrugRequests`, `getBids`, `submitBid`, `acceptBid`, `getPharmaCompanies`
- **Crowdfunding**: `getCampaign`
- **Account**: `getMe`

## Status values in use (inconsistent)

- **Submission and pipeline:** `queued`, `running`, `processing`, `awaiting_ai`, `complete`, `completed`, `failed`, `error`. Both `complete` and `completed` appear, and so do both `failed` and `error`. The StatusPill must normalise them:

  | Raw values | Pill |
  |---|---|
  | `queued` | Queued |
  | `running`, `processing`, `awaiting_ai` | Analyzing |
  | `complete`, `completed` | Complete |
  | `failed`, `error` | Failed |

- **Upload UI:** `uploading`, `submitting`, `success`, `error`.
- **Marketplace:** `draft`, `accepted`, `rejected`, `closed`, `locked`.
- **No "needs review" state** exists in submissions. The closest signal is `oncologist_reviewed: false` on a completed result. Don't invent the state; show "Awaiting oncologist review" from that boolean.

## Demo mode

- `NEXT_PUBLIC_ENABLE_DEMO_AUTH=1` bypasses Keycloak.
- The case is `demo-nsclc-kras-g12c`: KRAS p.Gly12Cys (LEVEL_1, targetable) and TP53 p.Arg175His (LEVEL_3B) in NSCLC.
- Ranked: Sotorasib and Adagrasib (`fda_approved`), Osimertinib (`repurposed`).
- The demo crowdfunding campaign tells a fictional patient's story ("María"). Anywhere it appears, it needs a visible "Demo" label.

## Routes (22)

- **Marketing / public:** `/`, `/explore`, `/gene/[symbol]`, `/login`
- **Core flow:** `/submit`, `/workspace`, `/results/[id]`, `/repurposing/[id]`, `/custom-drug/[id]`, `/dashboard`, `/oncologist`
- **Marketplace and funding:** `/marketplace`, `/marketplace/requests`, `/marketplace/requests/new`, `/crowdfund/[id]`, `/orders`, `/dashboard/campaigns`, `/admin/pharma`
- **System:** `error`, `not-found`

## Existing pieces to review before replacing

- **Hero components:** `components/hero/` (CaseCluster, CasePanel, PipelineFilmstrip, CyclingHeadline, CredibilityStrip, CommitStrip, CiteThisWork).
- **Genomic visuals:** `components/ui/genomic-stream.tsx`, `components/ui/logo-animated.tsx`.
- **Result sections:** `components/workspace/` (RankBarChart, DrugResultsSection, PipelineStageCard, StageOutputs), `CombinationTable`, `ImmunoPanel`, `SignatureCard`, `SampleQCCard`, `ResultsSkeleton`.
- **Earlier token direction:** the commented example in `BACKLOG.md` (OO-N) names a green and cream system: `#0F6E56`, `#FAFAF8`, `#16181D`, `#E4E2DB`.

## Implications for the redesign

1. **The hero can use real data.** "Evidence, assembled" maps directly:
   - the variant is `mutations[0]` (KRAS p.Gly12Cys, LEVEL_1);
   - the evidence chips are `candidates[].evidence_sources`;
   - the ranked list is `candidates` by `rank_score` with `drug_tier` labels;
   - the closing card uses `plain_language_summary`, including its oncologist-review sentence.

   Label it as the demo case.
2. **Copy must not say "cited".** `evidence_sources` are source names, not links or references. Use "names the source behind every ranking", or add per-source links to the backend first.
3. **The palette test gets a third option:** the existing green and cream direction from `BACKLOG.md`, next to the H&E and ink-plus-violet palettes.
4. **Scope is larger than the plan assumed** (22 routes, not 5). The redesign covers, in order:
   - `/` and `/results/[id]` with `/repurposing/[id]`;
   - then `/submit`, `/workspace`, `/dashboard`;
   - then the remaining routes.

   Marketplace, crowdfunding, orders and admin come last.
5. **Backend later:**
   - type `mutations` properly;
   - add a per-source reference URL to `evidence_sources`;
   - unify the status vocabulary (`complete`/`completed`, `failed`/`error`).
