# Drug Decision Logic — OpenOncology

This document explains exactly what the algorithm does when it encounters an
FDA-approved drug, a non-FDA-but-usable drug, or falls back to custom drug
discovery. It is the reference for contributors working on the ranking engine.

---

## Overview: The Three-Tier Decision Tree

```
Variant detected
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  Tier 1 — FDA-approved targeted therapy              │
│  OncoKB Level 1 or 2 for this variant + cancer type  │
└──────────────────────────────────────────────────────┘
       │ found?
       ├─ YES → Return with drug_tier="fda_approved"
       │         flag is_fda_approved=True
       │         include label reference + trial ID
       │
       ▼ none found
┌──────────────────────────────────────────────────────┐
│  Tier 2 — Repurposed / off-label / investigational   │
│  Drug approved for different indication but has       │
│  mechanistic rationale for this variant              │
└──────────────────────────────────────────────────────┘
       │ found?
       ├─ YES → Return with drug_tier="repurposed"
       │         flag is_fda_approved=False
       │         include repurposing_rationale
       │         include clinical_trial_ids if available
       │         UI shows amber badge "Off-label / Repurposing"
       │
       ▼ none found
┌──────────────────────────────────────────────────────┐
│  Tier 3 — Custom drug discovery (v1: brief only)     │
│  Generate target brief from ChEMBL + OpenTargets     │
│  Pharma marketplace → synthesis → crowdfund path     │
└──────────────────────────────────────────────────────┘
       └─ Return discovery_brief with drug_tier="custom_discovery"
           UI shows "Custom Drug Discovery" section
           NOTE: v1 defers custom drug work — brief is research-only
```

---

## Tier 1 — FDA-Approved Targeted Therapy

### What counts as Tier 1

| Criterion | Value |
|-----------|-------|
| OncoKB evidence level | LEVEL_1 or LEVEL_2 |
| FDA approval type | Full approval or Accelerated approval |
| Resistance gate | Drug must NOT be in resistance list for this mutation |

Examples:
- EGFR L858R + NSCLC → Osimertinib (FLAURA trial, FDA 2018)
- BRAF V600E + Melanoma → Dabrafenib + Trametinib (FDA 2014)
- NTRK1/2/3 FUSION → Larotrectinib, Entrectinib, Repotrectinib (tumour-agnostic)

### Response fields

```json
{
  "drug_name": "Osimertinib",
  "drug_tier": "fda_approved",
  "is_fda_approved": true,
  "oncokb_level": "LEVEL_1",
  "fda_approval_date": "2018-04-18",
  "approval_indication": "EGFR-mutated NSCLC (first-line)",
  "key_trial": "FLAURA",
  "resistance_note": null,
  "rank_score": 0.92,
  "evidence_completeness": "HIGH"
}
```

### Resistance hard gate

If a drug has an `LEVEL_R1` or `LEVEL_R2` entry for the detected mutation, it
is **excluded from Tier 1 output even if it appears at L1 for the gene** in
another context. Examples:

| Mutation | Drug blocked | Reason |
|----------|-------------|--------|
| EGFR T790M | Erlotinib, Gefitinib | Acquired resistance |
| EGFR C797S | Osimertinib | Third-generation resistance |
| KIT D816V | Imatinib | Intrinsic resistance |
| PDGFRA D842V | Imatinib | Intrinsic resistance |

---

## Tier 2 — Repurposed / Off-label / Investigational

### What counts as Tier 2

A drug enters Tier 2 when:
1. It is FDA-approved for **any** indication (not necessarily this one), AND
2. It has mechanistic evidence for the detected variant via at least one of:
   - OpenTargets association score ≥ 0.3
   - ChEMBL bioactivity annotation for this target
   - OncoKB Level 3A/3B or Level 4
   - CIViC evidence tier C or above
   - Phase 1/2 clinical trial for this mutation class

### Scoring within Tier 2

Repurposed candidates are scored by the same composite engine as Tier 1 drugs
(DiffDock binding + OpenTargets + clinical phase + CIViC), but with a
**0.15 down-weight on the OncoKB component** because L3/4 evidence is less
certain than L1/2.

The output response carries:
```json
{
  "drug_name": "Metformin",
  "drug_tier": "repurposed",
  "is_fda_approved": true,
  "approved_indication": "Type 2 diabetes",
  "repurposing_rationale": "AMPK activation inhibits mTORC1, relevant for PI3K/AKT pathway co-mutation",
  "oncokb_level": "LEVEL_4",
  "evidence_quality": "INVESTIGATIONAL",
  "disclaimer": "This drug is not approved for oncology. Clinical benefit for this mutation is not established. Oncologist review required before any use.",
  "clinical_trials": ["NCT02109549"],
  "rank_score": 0.51
}
```

### What v1 does NOT include in Tier 2

- Drugs withdrawn from the market (e.g. mobocertinib, withdrawn Nov 2023)
- Drugs with only in-vitro evidence and no human trial data
- Drugs flagged as reproductive hazards without oncology benefit evidence
- Unapproved drug candidates without IND on file

---

## Tier 3 — Custom Drug Discovery (v1 scope note)

### v1 design decision

> **OpenOncology v1 intentionally defers advanced custom drug work.**
> The priority is to perfect the Tier 1 and Tier 2 evidence-based engines first.
> Tier 3 generates a **research-grade discovery brief only** — it is not a
> clinical candidate generator. Any compound emerging from this path requires
> complete preclinical and clinical development (typically 10–15 years) before
> patient use.

### What Tier 3 does in v1

When no Tier 1 or Tier 2 match exists:

1. **Target brief** — Queries ChEMBL and OpenTargets for known ligands of the
   mutant protein pocket; scores by Lipinski Ro5 (oral exposure) and
   ADME/toxicity flags.

2. **Structural context** — If an AlphaFold structure is available for the
   protein, highlights the mutation's location relative to known binding pockets.

3. **Lead molecules** — Returns top-3 ChEMBL hits ranked by selectivity and
   bioactivity, flagged clearly as research leads, not clinical candidates.

4. **Marketplace brief** — Packages the above into a synthesis brief that can
   be submitted to the pharma marketplace for manufacturer bids.

### What Tier 3 does NOT do (v1 deferred items)

| Deferred feature | Target version | Reason deferred |
|-----------------|---------------|-----------------|
| De novo molecule generation (GNN/diffusion) | v2 | Requires extensive safety validation framework |
| ADME/PK prediction beyond Ro5 | v2 | Needs validated QSAR model, not just Lipinski |
| Multi-step synthesis planning | v2 | Requires retrosynthesis AI (ASKCOS/AiZynthFinder) |
| Animal model recommendation | v2 | Regulatory complexity |
| Automatic IND filing preparation | v3 | Requires institutional review |

---

## Handling the three tiers together: response contract

The API always returns all tiers it can populate, ranked within each tier:

```json
{
  "result_id": "...",
  "variant": "EGFR L858R",
  "cancer_type": "NSCLC",
  "decision_path": "tier1_found",
  "tiers": {
    "fda_approved": [
      { "drug_name": "Osimertinib", "rank_score": 0.92, ... },
      { "drug_name": "Erlotinib",   "rank_score": 0.74, ... }
    ],
    "repurposed": [
      { "drug_name": "Afatinib",    "rank_score": 0.61, "note": "approved for EGFR-mutated NSCLC but 2nd-line after osimertinib" }
    ],
    "custom_discovery": null
  },
  "top3_recommendation": ["Osimertinib", "Erlotinib", "Gefitinib"],
  "primary_tier": "fda_approved",
  "oncologist_review_required": true
}
```

`decision_path` values:
- `"tier1_found"` — at least one FDA-approved targeted therapy exists
- `"tier2_only"` — no FDA-approved match, repurposing candidates returned
- `"tier3_escalation"` — no targeted or repurposable match, discovery brief generated
- `"abstain"` — no actionable mutation found (negative control behaviour)

---

## Repurposing algorithm vs. other tools

| Tool | Approach | Coverage | Transparency |
|------|----------|----------|-------------|
| **OpenOncology Tier 2** | Composite score: ChEMBL + OpenTargets + OncoKB L3/4 + trial phase | Pan-cancer, variant-level | Full audit trail per drug |
| DrugBank Interactions | Drug–target interactions from curated DB | Target-level, not variant-level | Limited |
| DGIdb | Gene–drug interactions, curated + computed | Gene-level | Good |
| OncoKB L3/4 | Expert curation | Variant-level | Excellent but narrow |
| CIVIC | Community curation | Variant-level | Good |
| OpenTargets | Genetics + somatic + expression | Target-level, broad | Very good |

OpenOncology's key differentiator: **variant-level specificity + multi-source
composite score + resistance gating + cancer-type context**. Most tools return
a flat gene→drug list; OpenOncology adjusts scores based on whether the
specific amino acid change (e.g. EGFR L858R vs EGFR exon19del) has separate
evidence, and whether a detected co-mutation creates resistance.

---

## Contributing to the drug decision logic

- Evidence table: `api/services/oncokb_evidence.py` — `_LEVEL_TABLE`
- Resistance gates: same file — entries with `"LEVEL_R1"` / `"LEVEL_R2"`
- Ranking weights: `api/ai/ranking_config.py`
- Tier classification logic: `api/ai/ranking.py` — `classify_drug_tier()`
- Response schema: `api/schemas/responses.py`

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full guide on adding a new
evidence source or drug tier.
