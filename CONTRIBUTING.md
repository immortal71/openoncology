# Contributing to OpenOncology

Thank you for your interest in contributing. OpenOncology is a research prototype — contributions that improve scientific rigour, test coverage, documentation, or developer experience are especially welcome.

> **Fastest start:** `git clone https://github.com/immortal71/openoncology.git && cd openoncology && docker-compose up --build`  
> For detailed setup, troubleshooting, and Windows steps see [docs/SETUP.md](docs/SETUP.md).

## Table of Contents

- [Development setup](#development-setup)
- [How to add a new evidence source](#how-to-add-a-new-evidence-source)
- [How to add an evidence entry (drug/variant)](#how-to-add-an-evidence-entry-drugvariant)
- [How to run benchmarks](#how-to-run-benchmarks)
- [How the scoring algorithm works](#how-the-scoring-algorithm-works)
- [Drug decision tiers](#drug-decision-tiers)
- [Code review requirements](#code-review-requirements)
- [Good first issues](#good-first-issues)
- [Reporting bugs](#reporting-bugs)

Related documentation:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system components and data flow
- [docs/DRUG_DECISION_LOGIC.md](docs/DRUG_DECISION_LOGIC.md) — FDA vs repurposed vs custom three-tier logic
- [docs/REPURPOSING_ALGORITHM.md](docs/REPURPOSING_ALGORITHM.md) — repurposing scoring + comparison with other tools
- [docs/METHODS.md](docs/METHODS.md) — full scientific methods

---

## Development setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional, for full-stack dev)

### Python backend

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows PowerShell

# Install dependencies
cd api
pip install -r requirements.txt

# Optional: install dev/test extras
pip install pytest pytest-asyncio httpx
```

### Environment variables

Copy `.env.example` to `.env` (or set these directly):

```bash
ONCOKB_API_TOKEN=<your free token from oncokb.org>   # enables live OncoKB API
OPENAI_API_KEY=<your key>                             # enables GPT-4o summaries
DATABASE_URL=sqlite:///./dev.db                       # or PostgreSQL for prod
```

### Run the API server

```bash
cd api
uvicorn main:app --reload
```

### Run the frontend

```bash
cd web
npm install
npm run dev
```

### Docker (full stack)

```bash
docker-compose up --build
```

---

## How to add a new evidence source

Evidence sources contribute a raw score in `[0.0, 1.0]` per candidate drug. Adding a new source takes ~5 steps:

### Step 1 — Add a weight to `EvidenceWeights`

Edit `api/ai/ranking_config.py`:

```python
@dataclass
class EvidenceWeights:
    binding: float = 0.25
    opentargets: float = 0.20
    oncokb: float = 0.25
    alphamissense: float = 0.10
    clinical_phase: float = 0.10
    civic: float = 0.10
    my_new_source: float = 0.0   # ← add with 0.0 initially, tune after validation
```

Also update `validate()` and `as_ordered_list()` in the same class.

### Step 2 — Add to the raw components list in `ranking.py`

In `compute_rank_score()`, add your source to `raw_components`:

```python
raw_components["my_new_source"] = components.get("my_new_source_score")
```

### Step 3 — Populate the score in your data pipeline

The `candidates` list passed to `rank_candidates()` must include `my_new_source_score` for each drug dict. This typically means:

1. Create a new service file `api/services/my_new_source.py`
2. Add an `annotate_candidates()` or equivalent function
3. Call it in the relevant route or worker (see `api/routes/submit.py`)

### Step 4 — Update the audit trail

In `rank_candidates()`, the `evidence_audit_trail` list per drug should include an entry for your new source:

```python
{"source": "my_new_source", "raw_score": ..., "effective_weight": ..., "confidence": ...}
```

### Step 5 — Add test cases

Add at least 3 gold-standard cases to `EXTENDED_GOLD_STANDARD_CASES` in `api/services/benchmark.py` that test your source's contribution. Run the ablation study before and after to verify marginal impact:

```python
from api.services.benchmark import run_ablation_sync, LEVEL_1_CASES
report = run_ablation_sync(cases=LEVEL_1_CASES[:30])
print(report.summary())
```

---

## How to add an evidence entry (drug/variant)

Adding a drug–variant pair to the evidence table (e.g. a newly FDA-approved drug)
takes 3 steps:

### Step 1 — Add to `_LEVEL_TABLE` in `api/services/oncokb_evidence.py`

```python
("GENE_NAME", "ALTERATION"): {
    "DrugName": "LEVEL_1",   # FDA-approved for this exact variant + cancer type
    "OtherDrug": "LEVEL_2",  # Guideline-recommended
},
```

Keys are `(gene_uppercase, normalised_alteration)`. Use
`_normalise_alteration()` to convert a human-readable variant like `"L858R"` to
its normalised form. For fusions use the form `"FUSION"` or `"GENE1-GENE2"`.

For cancer-type-specific levels, add to `_CANCER_CONTEXT_OVERRIDES`:

```python
("BRAF", "V600E", "Colorectal Cancer"): {
    "Encorafenib": "LEVEL_1",
    "Cetuximab": "LEVEL_1",
},
```

### Step 2 — Add or update the benchmark case

Add a case to `HARD_CLINICAL_CASES` in `api/services/benchmark.py`:

```python
BenchmarkCase(
    case_id="HC_BRAF_V600E_CRC",
    gene="BRAF", alteration="V600E",
    cancer_type="Colorectal Cancer",
    known_drugs=["Encorafenib", "Cetuximab"],
    description="BRAF V600E CRC — BEACON-CRC trial",
),
```

**Benchmark integrity rules:**
- Never add a case by checking algorithm output first (that is data leakage)
- `known_drugs` must be sourced from FDA approval or published clinical guidelines
- Never expand `known_drugs` to manufacture a higher P@3 score
- Include the source trial ID or publication in the description

### Step 3 — Run the gate and confirm PASS

```bash
python scripts/hard_benchmark_gate.py
# Expected: Gate result: PASS
```

If the gate fails, investigate before adding more cases. Do not lower the gate
threshold.

---

## Drug decision tiers

All evidence entries should be assigned the correct tier. See
[docs/DRUG_DECISION_LOGIC.md](docs/DRUG_DECISION_LOGIC.md) for full details.
Quick reference:

| OncoKB level | Drug tier | Meaning |
|-------------|----------|---------|
| LEVEL_1 | `fda_approved` | FDA-approved for this variant + cancer type |
| LEVEL_2 | `fda_approved` | Standard of care / guideline-recommended |
| LEVEL_3A | `repurposed` | Clinical evidence in different cancer type |
| LEVEL_3B | `repurposed` | Evidence from case reports / small trials |
| LEVEL_4 | `repurposed` | Biological rationale, limited clinical data |
| LEVEL_R1 | — | Known resistance — drug is blocked for this variant |
| LEVEL_R2 | — | Putative resistance |

**Withdrawn drugs** must not be added (or must be removed if already present):
- Mobocertinib (Takeda, Nov 2023 — EXCLAIM-2 failed)
- Belzutifan in non-approved contexts until full label review

---

## How to run benchmarks

### Unit / integration tests

```bash
cd api
python -m pytest tests/ -v
```

### Benchmark suite (retrospective validation)

```bash
python -c "
from api.services.benchmark import run_benchmark_sync
report = run_benchmark_sync()
print(report.summary())
"
```

### Resistance test suite

```bash
python -c "
import asyncio
from api.services.benchmark import run_resistance_suite, resistance_suite_summary, RESISTANCE_TEST_CASES
results = asyncio.run(run_resistance_suite(RESISTANCE_TEST_CASES))
print(resistance_suite_summary(results))
"
```

### Ablation study (marginal source contribution)

```bash
python -c "
from api.services.benchmark import run_ablation_sync, LEVEL_1_CASES
report = run_ablation_sync(cases=LEVEL_1_CASES)
print(report.summary())
"
```

> **Note**: The full benchmark suite makes live API calls to OncoKB and OpenTargets. Set `ONCOKB_API_TOKEN` or the suite will use the static fallback table. Results may differ slightly between runs due to live API updates.

### CI integration

The test suite is configured for `pytest`. To add benchmarks to CI:

```yaml
# .github/workflows/test.yml (example)
- run: cd api && python -m pytest tests/ -v
```

For the slower benchmark suite, run it in a nightly job rather than on every PR.

---

## How the scoring algorithm works

The full ranking methodology is documented in [docs/METHODS.md](docs/METHODS.md). Here is a brief summary:

### Evidence sources (6 channels)

| Source | Weight | What it contributes |
|---|---|---|
| DiffDock (binding) | 0.25 | Predicted binding affinity from molecular docking (GPU pipeline; absent in default demo) |
| OncoKB | 0.25 | Clinical evidence tier (Level 1 = FDA-approved → Level 4 = biological rationale) |
| OpenTargets | 0.20 | Target-disease association score across genetics, somatic mutations, expression |
| AlphaMissense | 0.10 | Pathogenicity score for the specific amino acid change |
| ClinicalPhase | 0.10 | Maximum clinical development stage of the drug for any indication |
| CIViC | 0.10 | Community-curated clinical variant interpretation |

### Post-hoc rules (applied after weighted mean)

1. **Resistance gate**: Any drug with `oncokb_level ∈ {LEVEL_R1, LEVEL_R2}` is capped at `rank_score ≤ 0.15`. This is the most safety-critical rule.
2. **Safety penalty**: Withdrawn drugs receive a −0.50 penalty; QSAR-flagged de-novo compounds receive up to −0.30.
3. **Diversity penalty**: Drugs with only a single non-trivial evidence source are multiplied by 0.78 to reduce false-high rankings.

### Weights are configurable

All magic numbers live in `api/ai/ranking_config.py`. To run with custom weights (e.g., an ablation study):

```python
from api.ai.ranking_config import RankingConfig, EvidenceWeights
from api.ai.ranking import rank_candidates

cfg = RankingConfig(weights=EvidenceWeights(oncokb=0.50, opentargets=0.30, civic=0.20,
                                             binding=0.0, alphamissense=0.0, clinical_phase=0.0))
ranked = rank_candidates(candidates, cfg=cfg)
```

---

## Code review requirements

All PRs that modify the following files require **at least 2 approvals** from maintainers before merge:

- `api/ai/ranking.py` — core scoring algorithm
- `api/ai/ranking_config.py` — weight constants
- `api/services/oncokb_evidence.py` — resistance designations are safety-critical

For all other files, 1 approval is sufficient.

Please ensure:
- New features include tests in `api/tests/`
- Changes to the benchmark set are accompanied by a benchmark run showing the impact
- The SYSTEM_LIMITATIONS list in `api/ai/ranking.py` is updated if a limitation is resolved

---

## Good first issues

These are well-scoped, self-contained tasks suitable for first-time contributors:

### Label: `good first issue`

1. **Add 10 more VUS negative-control cases to `benchmark.py`**  
   Pick variants from OncoKB that have no Level 1/2 evidence and verify the system returns no over-claimed drugs.  
   _Skills needed_: Python, oncology knowledge helpful but not required.

2. **Add `test_ranking.py` unit tests for `compute_rank_score()`**  
   Test all 3 post-hoc rules (resistance gate, safety penalty, diversity penalty) with synthetic inputs.  
   _Skills needed_: Python, pytest.

3. **Add `estimate_aqueous_solubility()` to `adme.py`**  
   Use the existing physicochemical fields (logP, MW, HBD, HBA) and the GSE model heuristic.  
   _Skills needed_: Python, basic cheminformatics.

4. **Add a PMKB evidence source stub**  
   Create `api/services/pmkb.py` with a `lookup_pmkb_tier()` function that queries the PMKB API (https://pmkb.weill.cornell.edu/api) and returns a tier label. Wire up the result as a note in `annotate_candidates()`.  
   _Skills needed_: Python, REST API calls.

5. **Improve the LLM prompt for oncologists**  
   The `_build_prompt()` function in `llm_explainer.py` currently targets patients. Add a separate `_build_oncologist_prompt()` that uses technical language and includes evidence tier details.  
   _Skills needed_: Python, prompt engineering.

6. **Fix the `PAINS_COMPOUND` SMARTS pattern for catechols**  
   The current catechol SMARTS (`Oc1ccccc1O`) is a known false-positive for many approved drugs. Replace with a better-calibrated pattern from the original Baell & Holloway paper.  
   _Skills needed_: Python, SMARTS chemistry.

---

## Reporting bugs

Please open a GitHub issue with:
- What you did (steps to reproduce)
- What you expected
- What actually happened (full error traceback if applicable)
- Python version, OS, and whether you have `ONCOKB_API_TOKEN` set

For **security vulnerabilities**, please email privately rather than opening a public issue.
