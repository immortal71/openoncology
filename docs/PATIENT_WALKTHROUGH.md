# OpenOncology — End-to-End Patient Walkthrough

> **Status**: Research prototype case illustration. Mutation data is derived from publicly
> available de-identified TCGA records (cBioPortal). No personal health information is used.
> This walkthrough is intended to make the pipeline tangible and to illustrate what a
> "Stage 2 drug brief" looks like in practice.

---

## Case Summary

| Field | Value |
|---|---|
| **Case alias** | DEMO-PT-KRAS-001 |
| **Cancer type** | Non-Small Cell Lung Cancer (Lung Adenocarcinoma) |
| **Primary mutation** | KRAS p.Gly12Cys (G12C) |
| **Co-mutation** | TP53 p.Arg175His (R175H) |
| **Genome build** | GRCh37 |
| **Sample source** | TCGA-05-4382 (cBioPortal, luad_tcga_pub — de-identified) |
| **VAF (KRAS)** | 0.41 |
| **Tumour purity** | ~55% (biopsy report) |

---

## Step 1 — Input: VCF File

The patient's tumour sequencing produces a standard VCF file. The two driver variants are shown
below in minimal VCF format:

```
##fileformat=VCFv4.2
##reference=GRCh37
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total read depth">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">
#CHROM  POS         ID  REF  ALT  QUAL  FILTER  INFO        FORMAT  SAMPLE
12      25398284    .   C    A    99    PASS    DP=146      GT:AF   0/1:0.41
17      7673803     .   G    A    93    PASS    DP=133      GT:AF   0/1:0.36
```

**Interpretation:**
- Chromosome 12, position 25398284: `C→A` encodes KRAS p.Gly12Cys (G12C) at VAF 41%.
- Chromosome 17, position 7673803: `G→A` encodes TP53 p.Arg175His (R175H) at VAF 36%.

---

## Step 2 — Sample QC

The pipeline first assesses sequencing quality:

```json
{
  "verdict": "PASS",
  "ffpe_score": 12.0,
  "ffpe_flagged": false,
  "tumour_purity_pct": 55,
  "total_variants": 2,
  "coverage_adequacy": "ADEQUATE",
  "recommendations": []
}
```

Both variants pass depth and VAF thresholds. Tumour purity at 55% is adequate for confident
somatic calling (purity threshold is 20%).

---

## Step 3 — Variant Annotation

Each variant is annotated against the OncoKB static table and external evidence sources:

| Variant | Gene | HGVS | SO Term | VAF | AlphaMissense | OncoKB Level |
|---|---|---|---|---|---|---|
| KRAS G12C | KRAS | p.Gly12Cys | missense_variant | 0.41 | 0.97 (pathogenic) | LEVEL_1 |
| TP53 R175H | TP53 | p.Arg175His | missense_variant | 0.36 | 0.99 (pathogenic) | — (no direct target) |

**Key annotation notes:**
- KRAS G12C at LEVEL_1: this is the exact variant targeted by sotorasib (CodeBreaK 100) and
  adagrasib (KRYSTAL-1), both FDA-approved for previously-treated NSCLC.
- TP53 R175H is a gain-of-function mutation. No FDA-approved drug directly targets TP53 in NSCLC;
  it is a co-driver that confers p53 pathway disruption.
- The co-mutation penalty logic notes TP53 R175H but does not suppress KRAS G12C evidence because
  TP53 operates in a separate pathway and is not a resistance mechanism to KRAS G12C inhibitors.

---

## Step 4 — Drug Ranking (Evidence Fusion)

The ranking engine queries OncoKB, OpenTargets, CIViC, and ChEMBL for KRAS G12C in NSCLC, then
fuses evidence using the weighted-mean algorithm (see `docs/METHODS.md`):

| Rank | Drug | OncoKB Level | OpenTargets Score | Rank Score | CI [low, high] | Confidence |
|---|---|---|---|---|---|---|
| **1** | **Sotorasib** | LEVEL_1 | 0.92 | **1.00** | [0.86, 1.00] | HIGH |
| **2** | **Adagrasib** | LEVEL_1 | 0.90 | **0.98** | [0.84, 1.00] | HIGH |
| 3 | Pembrolizumab | LEVEL_1 (TMB-H) | 0.75 | 0.62 | [0.48, 0.76] | MEDIUM |

Sotorasib and adagrasib both achieve rank_score = 1.00 / 0.98 because:

1. **Resistance gate** — Neither has an R1/R2 resistance flag for G12C.
2. **OncoKB floor** — LEVEL_1 evidence applies a hard minimum rank_score floor of 0.90 before
   post-hoc adjustments.
3. **Evidence completeness** = 0.80 (OncoKB + OpenTargets present; DiffDock and AlphaMissense
   absent — typical for demo without GPU pipeline, so half-width of CI is 0.14).

---

## Step 5 — Stage 2 Drug Brief (Oncologist-Facing Output)

Below is the Stage 2 precision-oncology brief that would accompany a tumor board presentation.
It is generated automatically by the pipeline and is intended for review by a licensed oncologist.

---

### PRECISION ONCOLOGY DRUG BRIEF
**Patient alias:** DEMO-PT-KRAS-001  
**Cancer type:** Non-Small Cell Lung Cancer (Lung Adenocarcinoma)  
**Report date:** May 2026  
**Pipeline version:** OpenOncology research prototype  

---

#### Actionable Variant

**KRAS p.Gly12Cys (G12C)**  
OncoKB Level: **1 — FDA-approved for this exact context**  
VAF: 41% | Tumour purity: 55% | Pathogenicity (AlphaMissense): 0.97 *(pathogenic)*

The KRAS G12C mutation is a constitutively activating substitution at the glycine-12 residue
that locks KRAS in a GTP-bound state. Unlike other KRAS mutations, G12C creates a cysteine that
can be targeted covalently by small-molecule inhibitors.

Co-mutation detected: **TP53 R175H** (gain-of-function; no approved targeted therapy in NSCLC;
does not alter KRAS G12C recommendation).

---

#### Tier 1 — FDA-Approved Drugs

| Drug | Indication | Trial | Evidence | Rank Score |
|---|---|---|---|---|
| **Sotorasib** (Lumakras) | KRAS G12C+ NSCLC, ≥1 prior line | CodeBreaK 100/200 | OncoKB LEVEL_1 | 1.00 |
| **Adagrasib** (Krazati) | KRAS G12C+ NSCLC, ≥1 prior line | KRYSTAL-1 | OncoKB LEVEL_1 | 0.98 |

**Clinical context:**
- Sotorasib (AMG 510): Phase 2 ORR 37%, DCR 81%, median DoR 11.1 months in CodeBreaK 100.
  Phase 3 CodeBreaK 200 vs docetaxel: PFS benefit (5.6 vs 4.5 mo; HR 0.66).
- Adagrasib (MRTX849): KRYSTAL-1 ORR 43%, median PFS 6.5 months; CNS activity reported.
- Both agents are irreversible covalent binders of the mutant cysteine in the switch-II pocket.
- Resistance mechanisms: KRAS G12C/Y96D secondary mutations, KRAS amplification, bypass via
  EGFR/MET/RAS/RAF alterations. Consider repeat biopsy at progression.

---

#### Tier 2 — Checkpoint Immunotherapy (Biomarker-Driven)

Pembrolizumab (Keytruda) is considered for cases with TMB-H (≥10 mut/Mb) or PD-L1 TPS ≥1%.
*This patient's PD-L1 TPS and TMB were not available in the input data.*  
Rank score: 0.62 (MEDIUM confidence; pending biomarker confirmation).

---

#### Resistance and Safety Flags

| Alert | Detail |
|---|---|
| No resistance mutations detected | KRAS G12C inhibitors are not resistance-flagged for this variant |
| STK11 co-mutation | *Not detected*; if present, would reduce immunotherapy benefit |
| hERG risk (sotorasib) | LOW — structure-based alert absent |
| Hepatotoxicity (adagrasib) | MODERATE — ALT elevation reported in ~15% of patients; monitor LFTs |

---

#### Recommended Next Steps (for oncologist review)

1. Confirm KRAS G12C on an orthogonal platform (e.g., ctDNA liquid biopsy) if tissue VAF
   borderline or sample quality suboptimal.
2. Send tumour for TMB and PD-L1 TPS to assess immunotherapy eligibility.
3. Consider molecular tumour board discussion for first-line vs. second-line context:
   - First-line: pembrolizumab ± chemotherapy remains standard; KRAS G12C inhibitors are
     currently indicated for ≥2nd-line (CodeBreaK 200 is 2nd-line setting).
   - Second-line and beyond: sotorasib or adagrasib are the preferred options.
4. Enrol in a clinical trial if available: KRAS G12C + TP53 co-mutation may be relevant for
   combination KRAS+SOS1 or KRAS+MEK trials.

---

#### Pipeline Audit Trail

```json
{
  "pipeline_version": "OpenOncology research prototype",
  "evidence_sources_queried": ["OncoKB", "OpenTargets", "CIViC", "ChEMBL"],
  "oncokb_mode": "static_fallback_120_entries",
  "alphamissense_loaded": true,
  "diffdock_available": false,
  "ranking_weights": {
    "oncokb": 0.25,
    "opentargets": 0.20,
    "alphamissense": 0.10,
    "clinical_phase": 0.10,
    "civic": 0.10,
    "diffdock": 0.25
  },
  "resistance_gate_applied": true,
  "safety_penalty_applied": true,
  "co_mutation_penalty": 0.0,
  "primary_metric": "rank_score",
  "confidence_intervals": "epistemic_from_missing_sources",
  "guardrail": "NOT a clinical decision support tool. All recommendations require independent oncologist verification."
}
```

---

## Reproducibility

To reproduce this walkthrough locally:

```bash
# 1. Create the VCF
cat > /tmp/demo_kras_g12c.vcf << 'EOF'
##fileformat=VCFv4.2
##reference=GRCh37
#CHROM  POS         ID  REF  ALT  QUAL  FILTER  INFO    FORMAT  SAMPLE
12      25398284    .   C    A    99    PASS    DP=146  GT:AF   0/1:0.41
17      7673803     .   G    A    93    PASS    DP=133  GT:AF   0/1:0.36
EOF

# 2. Run the demo pipeline
python scripts/run_demo.py \
  --vcf /tmp/demo_kras_g12c.vcf \
  --cancer-type "Non-Small Cell Lung Cancer" \
  --out /tmp/demo_kras_g12c_output.json

# 3. View the drug ranking
python -c "
import json
data = json.load(open('/tmp/demo_kras_g12c_output.json'))
for drug in data['repurposing'][:3]:
    print(drug['drug_name'], drug['rank_score'], drug.get('oncokb_level'))
"
```

---

## Caveats and Limitations

1. **Not a clinical decision-support tool.** This report is generated by a research prototype
   that has not been validated in a clinical setting, is not CLIA/CAP certified, and must not
   be used to make treatment decisions without independent oncologist review.
2. **OncoKB static fallback.** Without a live OncoKB API token, the pipeline uses a ~120-entry
   static table. Live-API mode provides broader and more up-to-date coverage.
3. **No DiffDock binding scores.** Molecular docking (DiffDock) requires GPU resources and is
   not run in the default demo. Confidence intervals are therefore wider (AlphaMissense and
   DiffDock sources both absent).
4. **KRAS G12C–specific.** Sotorasib and adagrasib covalently bind the G12C cysteine and are
   inactive against G12D, G12V, or other KRAS variants.
5. **Co-mutation complexity.** TP53 R175H is a prognostic marker but is not directly actionable
   in this context. Complex co-mutation landscapes (e.g., G12C + MET amplification) may reduce
   KRAS inhibitor efficacy and should be discussed at a molecular tumour board.
