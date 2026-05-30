# Repurposing Algorithm — OpenOncology

OpenOncology's drug repurposing module finds FDA-approved drugs from
non-oncology indications that have mechanistic evidence for a given
cancer-driving mutation.

---

## Why repurposing matters

FDA approval for a new cancer indication takes 10–15 years and costs > $1B.
Hundreds of already-approved drugs have molecular evidence for cancer targets
but no oncology label. The repurposing engine systematically surfaces these
candidates at the variant level, with an evidence-backed composite score and
explicit uncertainty labelling.

---

## Algorithm design

### Inputs

| Input | Source |
|-------|--------|
| Mutant gene + alteration | Patient VCF → variant calling |
| Cancer type | Patient-reported or inferred from clinical context |
| Actionable variants | `oncokb_evidence._LEVEL_TABLE` lookup |
| Drug-target annotations | ChEMBL REST API |
| Target-disease associations | OpenTargets GraphQL API |
| Clinical trial matches | ClinicalTrials.gov API |
| Binding scores | DiffDock (when AlphaFold structure available) |

### Step 1 — Candidate generation

For each actionable gene, query ChEMBL for all compounds with:
- Activity type in {IC50, Ki, Kd, EC50}
- Assay type = binding or functional
- Standard activity value ≤ 10 µM (broad initial net)

Then filter to compounds that are:
- FDA-approved (ChEMBL `max_phase = 4`) for any indication
- Not already in the Tier 1 output for this variant

### Step 2 — Evidence scoring (4 sources)

```
repurposing_score =
    0.35 × opentargets_score          # target-disease association
  + 0.30 × binding_evidence_score     # ChEMBL + DiffDock
  + 0.20 × clinical_phase_score       # trial evidence for this indication
  + 0.15 × civic_score                # community curation quality
```

| Source | Score range | What 1.0 means |
|--------|------------|----------------|
| OpenTargets | 0–1 | Overall association (genetics + somatic + expression) |
| Binding evidence | 0–1 | ChEMBL IC50 ≤ 100 nM = 1.0; 10 µM = 0.0; + DiffDock bonus |
| Clinical phase | 0–1 | Phase 3 = 0.9, Phase 2 = 0.5, Phase 1 = 0.2, case report = 0.1 |
| CIViC | 0–1 | Tier A = 1.0, B = 0.75, C = 0.5, D = 0.25 |

### Step 3 — Repurposing confidence classification

```
repurposing_score ≥ 0.60  →  confidence = "SUPPORTED"
0.35 ≤ score < 0.60       →  confidence = "EXPLORATORY"
score < 0.35               →  confidence = "WEAK" (not shown by default)
```

### Step 4 — Hard gates (exclusions)

A repurposing candidate is excluded regardless of score if:
1. The drug appears in the **resistance table** for this variant
2. The drug was **withdrawn from market** (mobocertinib Nov 2023, aducanumab, etc.)
3. The drug has a **black-box warning** that directly contradicts this tumour type
4. The drug is **pregnancy category X** without documented oncology use

### Step 5 — Disclaimer generation

Every repurposed drug automatically gets a disclaimer:

```
"[Drug name] is FDA-approved for [approved indication] but is not approved
for this cancer type or mutation. Clinical benefit is [SUPPORTED / EXPLORATORY]
based on [evidence sources]. Oncologist review is required before any
clinical decision."
```

---

## Response structure

```json
{
  "result_id": "abc-123",
  "repurposing_candidates": [
    {
      "rank": 1,
      "drug_name": "Everolimus",
      "chembl_id": "CHEMBL1004",
      "drug_tier": "repurposed",
      "approved_indication": "Renal cell carcinoma, breast cancer (HR+), subependymal giant cell astrocytoma",
      "repurposing_rationale": "mTOR inhibition — relevant for PI3K/PTEN-altered tumours",
      "rank_score": 0.72,
      "repurposing_confidence": "SUPPORTED",
      "evidence_breakdown": {
        "opentargets_score": 0.68,
        "binding_evidence_score": 0.85,
        "clinical_phase_score": 0.70,
        "civic_score": 0.60
      },
      "clinical_trials": ["NCT01107intf", "NCT02395..."],
      "disclaimer": "Everolimus is FDA-approved for renal cell carcinoma but is not approved for this mutation/cancer combination...",
      "is_fda_approved": true,
      "is_oncology_approved": true,
      "oncologist_review_required": true
    }
  ],
  "scope_note": "Version 1 focuses on FDA-approved repurposable drugs with mechanistic rationale. Custom drug synthesis is a research tool only and is deferred to v2."
}
```

---

## Comparison with other tools

| Dimension | OpenOncology | DGIdb | DrugBank | OpenTargets | PanDrugs |
|-----------|-------------|-------|----------|------------|---------|
| **Variant-level specificity** | Yes — per amino acid change | No — gene-level | No — gene-level | Partial — somatic hotspots | Partial |
| **Cancer-type context** | Yes — context overrides per tumour | No | No | Partial | Yes |
| **Composite scoring** | Yes — 4-source weighted | No | No | Association score only | Pantumor priority score |
| **Resistance gating** | Yes — hard exclusions | No | No | No | Partial |
| **FDA withdrawal tracking** | Yes — mobocertinib removed Nov 2023 | Lagging | Lagging | Lagging | Lagging |
| **Audit trail per drug** | Full source breakdown | No | No | Partial | No |
| **Trial linkage** | Yes — ClinicalTrials.gov live | No | No | Yes | Yes |
| **Open-source** | Yes (MIT) | Yes (MIT) | No (commercial) | Yes | No |

### Key advantages of OpenOncology's approach

1. **Variant-level not gene-level** — KRAS G12C gets different candidates
   than KRAS G12D because the evidence table differentiates them.

2. **Resistance is a first-class citizen** — A drug is suppressed if the
   detected mutation is a known resistance mechanism, even if the drug is
   otherwise relevant to the gene.

3. **Cancer-type context** — Same mutation (e.g. BRAF V600E) has different
   approved drugs in melanoma vs CRC vs NSCLC; the algorithm adjusts.

4. **Source diversity bonus** — A drug with evidence from 3+ independent
   sources gets a diversity score boost.

5. **Full transparency** — Every recommendation exposes the exact per-source
   scores so an oncologist can evaluate provenance.

### Known limitations

- DiffDock binding scores are only available when an AlphaFold structure
  is annotated in the pipeline; ~30% of mutations fall back to ChEMBL-only.
- OpenTargets GraphQL rate limit means live scoring is cached for 24h;
  newly published associations lag by up to 1 day.
- Clinical trial matching is keyword-based and may over-match broad terms
  like "solid tumours"; trial team review is always recommended.

---

## Custom drug discovery (v1 research tool)

When no Tier 1 or Tier 2 candidates exist, the system generates a discovery
brief from ChEMBL + AlphaFold structural analysis. This is provided as a
**research starting point only**. Any compound identified here:

- Has not been tested in clinical trials for this indication
- Requires full preclinical development (cell lines, PDX models, toxicology)
- Requires IND filing before any human use
- Typically takes 10–15 years from this point to patient availability

The custom drug pathway feeds into the **marketplace module** where pharma
companies can bid on synthesis contracts, and the **crowdfunding module**
where patient communities can fund research. Both are infrastructure support
tools, not clinical decision support.

---

## Adding repurposing evidence

To manually add a repurposing candidate with known evidence:

1. Add an entry to `_LEVEL_TABLE` in `api/services/oncokb_evidence.py` at
   the appropriate OncoKB level (Level 3A/3B for off-label with clinical data,
   Level 4 for biological rationale only).

2. Run the benchmark gate: `python scripts/hard_benchmark_gate.py`

3. Submit a PR with the clinical reference (trial ID or publication DOI).

See [CONTRIBUTING.md](../CONTRIBUTING.md) for full details.
