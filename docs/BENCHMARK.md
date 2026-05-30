# OpenOncology — Benchmark Reference

This document is the authoritative reference for all benchmark numbers.
There are **two distinct benchmark contexts** and they must never be conflated:

| Context | Description |
|---------|-------------|
| **PRE-PUBLICATION** | The blinded 50-case holdout used in the preprint. Frozen. |
| **POST-PUBLICATION** | The ongoing hard clinical gate on main. Updated as evidence expands. |

---

## ⚠️ Integrity rules

- Numbers in this file are sourced directly from gate artifacts (`hard_benchmark_results.json`) or from the published validation run (`validation_results/holdout_50_metrics.json`).  
- Never edit numbers here to match desired output — run the gate and copy what it prints.  
- Never add benchmark cases by checking algorithm output first. Cases must be clinically sourced.  
- Never expand `known_drugs` in a benchmark case to manufacture a P@3 gain.  
- The pre-publication numbers are **frozen** — they reflect the exact system described in the preprint and cannot be retroactively improved.

---

## PRE-PUBLICATION baseline (published in preprint)

**Citation:** Kharel, A. (2026). *OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision Oncology.* Research Square. https://doi.org/10.21203/rs.3.rs-9707913/v1

**Run command used:**
```bash
python scripts/blind_external_validation.py --n-cases 50 --seed 11
```
Mode: OncoKB static fallback · no live CIViC · offline  
Artifact: `validation_results/holdout_50_metrics.json`

### Blinded 50-case oncologist holdout

| Metric | Value | Notes |
|--------|-------|-------|
| **Hit@3** | **0.900** | Gold-standard drug in top-3 for 90% of cases |
| **Standard Precision@3** | **0.508** | Ceiling for this mixed-difficulty holdout: **0.650** |
| **Normalised Precision@3** | **0.817** | Near-perfect when normalised for single-drug gold standards |
| **False Positives** | **0** | FP rate 0% — no spurious high-confidence recommendations |
| **Mean Reciprocal Rank (MRR)** | **0.883** | Gold drug appears near the top on average |
| **NDCG@3** | **0.845** | Strong ranking quality across the full holdout |

**Holdout composition:** 40 sensitivity cases (12 single-drug gold standard, 28 multi-drug gold standard) + 10 negative-control specificity cases.  
**Source material:** JCO Precision Oncology, Annals of Oncology, Nature Medicine tumour board reports.  
**Full case list:** `validation_results/holdout_50_results.txt`

> **Why Standard P@3 = 0.508 while Hit@3 = 0.900?** Standard P@3 uses a fixed denominator of 3 regardless of how many gold-standard drugs exist. When a case has only one gold-standard drug, even a perfect top-3 result gives P@3 = 1/3 = 0.333. Most cases in precision oncology have a single targetable drug per mutation — this is expected behaviour, not a failure. The ceiling of 0.650 reflects the realistic maximum for this holdout's case mix.

---

## POST-PUBLICATION ongoing benchmark (hard gate, main branch)

**Run command:**
```bash
python scripts/hard_benchmark_gate.py
```
Mode: OncoKB static fallback · offline (no live API calls required)  
Artifact: `hard_benchmark_results.json` (updated on every gate run)

### Current hard clinical gate — last run 2026-05-29

| Metric | Value | Gate threshold | Status |
|--------|-------|----------------|--------|
| **Standard P@3** | **0.8178** (≈ 0.818) | ≥ 0.65 | ✅ PASS |
| **Hit@3** | **100.0%** | ≥ 90% | ✅ PASS |
| **False Positives** | **0** | ≤ 0 | ✅ PASS |
| Cases | 83 total | — | 75 sensitivity + 8 negative controls |

> **Why is post-pub P@3 higher than the paper?** The hard gate cases are curated specifically for the gate (known difficult variants, not a random holdout). The 50-case blinded holdout was drawn blindly from literature — a harder, more representative clinical mix. These are different benchmarks measuring different things. Do not compare the numbers directly.

### Change log (post-publication improvements)

| Date | Change | P@3 before | P@3 after |
|------|--------|-----------|-----------|
| 2026-05-03 | Repotrectinib NTRK evidence; EGFR exon20ins bug fix | ~0.800 | 0.817 |
| 2026-05-29 | FGFR2-BICC1/FGFR3-TACC3 aliases; CLDN18/DLL3/FOLR1 evidence + context overrides | 0.817 | 0.8178 |

---

## TCGA real-patient coverage benchmarks

These are coverage benchmarks (does the system return *any* drug candidate?), not ranked-retrieval benchmarks.

### 100-case TCGA cohort

```bash
python scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json
```

| Tier | Patients | % |
|------|----------|---|
| Tier 1 — FDA-approved direct match | 36 | 36% |
| Tier 2 — Repurposing candidate | 64 | 64% |
| **Total covered** | **100** | **100%** |

Artifact: [real_patient_benchmark_100.json](../real_patient_benchmark_100.json)

### 200-case TCGA cohort

```bash
python scripts/fetch_real_patients.py --n 200 --out-json real_patient_benchmark_200.json
```

| Tier | Patients | % |
|------|----------|---|
| Tier 1 — FDA-approved direct match | 15 | 7.5% |
| Tier 4 — Custom-design escalation path | 185 | 92.5% |
| **Total covered** | **200** | **100%** |

The 200-patient set is intentionally harder and includes many variants with no direct approved match — useful for evaluating escalation behaviour and safe abstention.

Artifact: [real_patient_benchmark_200.json](../real_patient_benchmark_200.json)

---

## How to run a verified benchmark

```bash
# 1. Activate environment
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate    # Linux/macOS

# 2. Run the hard gate (results go to hard_benchmark_results.json)
python scripts/hard_benchmark_gate.py

# 3. Run the blinded 50-case holdout (replicates the paper run)
python scripts/blind_external_validation.py --n-cases 50 --seed 11

# 4. Real-patient coverage benchmark
python scripts/fetch_real_patients.py --n 100 --out-json real_patient_benchmark_100.json
python scripts/fetch_real_patients.py --n 200 --out-json real_patient_benchmark_200.json
```

---

## Metric definitions

| Metric | Formula | Notes |
|--------|---------|-------|
| **Standard P@3** | (hits in top-3) / 3 | Fixed denominator = 3. Penalises single-drug gold standards. Use for comparison across systems. |
| **Normalised P@3** | (hits in top-3) / min(3, \|gold\|) | Denominator = number of gold drugs (≤3). Rewards systems that correctly identify all relevant drugs. |
| **Hit@3** | 1 if ≥1 gold drug in top-3, else 0 | Binary retrieval success. Clinical relevance metric. |
| **MRR** | 1 / rank_of_first_hit | Mean over all cases. Rewards ranking the correct drug higher. |
| **NDCG@3** | Discounted cumulative gain at k=3 | Graded relevance; penalises correct drugs appearing lower in the list. |
| **False Positive** | High-confidence recommendation with no evidence support | Defined per-case in benchmark spec. Gate requires FP = 0. |
