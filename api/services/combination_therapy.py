"""Combination Therapy Scoring — OpenOncology

Identifies clinically-rational drug combinations from the individual ranked
candidates by checking for:
  1. Synergistic pathway coverage — two drugs hitting different nodes of the
     same dysregulated pathway (e.g. BRAF + MEK, CDK4/6 + ER, EGFR + MET).
  2. Known approved combination regimens — curated FDA-approved combos.
  3. Resistance bypass combinations — adding a second agent to prevent/overcome
     acquired resistance (e.g. EGFR TKI + RAS bypass inhibitor).

Usage in the pipeline
─────────────────────
  After rank_candidates() produces individual ranked drugs, call
  score_combinations(ranked_drugs, mutations) to produce a
  CombinationResult list for display alongside single-agent recommendations.

References
──────────
  - FDA-approved combination labels (reviewed 2025)
  - Planchard et al., Lancet Oncol 2016 (dabrafenib + trametinib, NSCLC)
  - Slamon et al., N Engl J Med 2015 (palbociclib + letrozole)
  - Tabernero et al., Lancet 2015 (encorafenib + cetuximab, CRC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class CombinationCandidate:
    """A two-drug (or three-drug) combination recommendation."""
    drugs: list[str]
    synergy_type: str           # "pathway_vertical", "bypass_resistance", "approved_regimen"
    synergy_rationale: str
    combination_score: float    # 0–1
    evidence_level: str         # "LEVEL_1", "LEVEL_2", "LEVEL_3A"
    evidence_note: str
    cancer_type_context: Optional[str] = None
    trial_ids: list[str] = field(default_factory=list)


# ── Curated approved combinations ─────────────────────────────────────────────
# Structure: (drug1_lower, drug2_lower) → CombinationCandidate template

_APPROVED_COMBINATIONS: list[dict] = [
    # ── BRAF/MEK vertical inhibition ──────────────────────────────────────────
    {
        "drugs": ["Dabrafenib", "Trametinib"],
        "synergy_type": "pathway_vertical",
        "synergy_rationale": "BRAF V600E drives MAPK via MEK1/2. Single BRAF inhibition causes paradoxical ERK reactivation via CRAF. Adding MEK inhibition suppresses rebound and improves OS/PFS.",
        "combination_score": 0.95,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved: melanoma, NSCLC (BRAF V600E), anaplastic thyroid, low-grade glioma. COMBI-d, COMBI-v, BRF113928 trials.",
        "trigger_genes": {"BRAF"},
        "trial_ids": ["NCT01584648", "NCT01597908"],
    },
    {
        "drugs": ["Encorafenib", "Binimetinib"],
        "synergy_type": "pathway_vertical",
        "synergy_rationale": "Longer-residence BRAF inhibitor (encorafenib) + MEK inhibition — improved PFS vs dabrafenib/trametinib in BRAF-mutant melanoma (COLUMBUS trial).",
        "combination_score": 0.93,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved for BRAF V600E/K melanoma. COLUMBUS trial (NCT01909453).",
        "trigger_genes": {"BRAF"},
        "trial_ids": ["NCT01909453"],
    },
    {
        "drugs": ["Encorafenib", "Cetuximab"],
        "synergy_type": "bypass_resistance",
        "synergy_rationale": "In CRC, BRAF V600E inhibition causes rapid EGFR-mediated reactivation of RAS. Adding anti-EGFR (cetuximab) blocks the bypass → durable response.",
        "combination_score": 0.90,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved for BRAF V600E metastatic CRC (BEACON trial, NCT02928224). Median OS 9.0 vs 5.4 months.",
        "trigger_genes": {"BRAF"},
        "cancer_type_context": "colorectal",
        "trial_ids": ["NCT02928224"],
    },
    # ── CDK4/6 + endocrine therapy ────────────────────────────────────────────
    {
        "drugs": ["Palbociclib", "Letrozole"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "CDK4/6 inhibition blocks G1→S transition in ER+ breast cancer; combined with aromatase inhibitor removes ligand driving ER-dependent transcription. Synergistic growth suppression.",
        "combination_score": 0.92,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved 1L ER+/HER2- advanced breast cancer. PALOMA-2 (NCT01978001) — PFS 24.8 vs 14.5 months.",
        "trigger_genes": {"CCND1", "CDK4", "CDK6", "ESR1", "RB1"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT01978001"],
    },
    {
        "drugs": ["Ribociclib", "Fulvestrant"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "CDK4/6 + selective estrogen receptor degrader (SERD) for ER+ breast cancer progressing on AI.",
        "combination_score": 0.90,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved 2L ER+/HER2- advanced breast cancer. MONALEESA-3 (NCT02422615).",
        "trigger_genes": {"CCND1", "CDK4", "CDK6", "ESR1"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT02422615"],
    },
    {
        "drugs": ["Abemaciclib", "Fulvestrant"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "Abemaciclib (more CDK4-selective, continuous dosing) + SERD in HR+/HER2- advanced breast cancer. Also approved as monotherapy.",
        "combination_score": 0.88,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved. MONARCH 2 trial (NCT02107703). PFS 16.4 vs 9.3 months.",
        "trigger_genes": {"CDK4", "CDK6", "ESR1", "CCND1"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT02107703"],
    },
    # ── HER2-targeted combos ──────────────────────────────────────────────────
    {
        "drugs": ["Tucatinib", "Trastuzumab", "Capecitabine"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "HER2 TKI (tucatinib) + trastuzumab + capecitabine for HER2+ breast cancer — triple combination covers HER2 at receptor, kinase domain, and DNA levels.",
        "combination_score": 0.92,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved for previously treated HER2+ breast cancer including brain mets. HER2CLIMB (NCT02614794). PFS 7.8 vs 5.6 months.",
        "trigger_genes": {"ERBB2"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT02614794"],
    },
    {
        "drugs": ["Pertuzumab", "Trastuzumab", "Docetaxel"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "Dual HER2 blockade (pertuzumab blocks dimerisation domain; trastuzumab blocks domain IV) plus chemotherapy. Prevents HER2/HER3 heterodimerisation bypass.",
        "combination_score": 0.93,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved 1L HER2+ metastatic breast cancer. CLEOPATRA (NCT00567190). OS 56.5 vs 40.8 months.",
        "trigger_genes": {"ERBB2"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT00567190"],
    },
    # ── EGFR + MET bypass ─────────────────────────────────────────────────────
    {
        "drugs": ["Osimertinib", "Savolitinib"],
        "synergy_type": "bypass_resistance",
        "synergy_rationale": "MET amplification is the most common (20-30%) bypass resistance mechanism to osimertinib in EGFR-mutant NSCLC. Adding MET inhibitor restores sensitivity.",
        "combination_score": 0.83,
        "evidence_level": "LEVEL_3A",
        "evidence_note": "TATTON trial (NCT02143466) showed 52% ORR in EGFR+/MET-amp post-osimertinib progression. Phase 3 SAVANNAH trial ongoing.",
        "trigger_genes": {"EGFR", "MET"},
        "trial_ids": ["NCT02143466"],
    },
    # ── PI3K/mTOR + endocrine ─────────────────────────────────────────────────
    {
        "drugs": ["Everolimus", "Exemestane"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "mTORC1 inhibition + AI for ER+/HER2- breast cancer progressing on non-steroidal AI. mTOR pathway is a major resistance bypass for endocrine therapy.",
        "combination_score": 0.85,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved. BOLERO-2 (NCT00863655). PFS 10.6 vs 4.1 months.",
        "trigger_genes": {"MTOR", "PIK3CA", "AKT1", "ESR1"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT00863655"],
    },
    {
        "drugs": ["Alpelisib", "Fulvestrant"],
        "synergy_type": "pathway_vertical",
        "synergy_rationale": "PI3Kα inhibition (alpelisib targets PIK3CA-mutant isoform) + SERD. PIK3CA mutation drives PI3K/AKT/mTOR → ER independence — combination suppresses both.",
        "combination_score": 0.88,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved for PIK3CA-mutated ER+/HER2- breast cancer. SOLAR-1 (NCT02437318). PFS 11.0 vs 5.7 months.",
        "trigger_genes": {"PIK3CA"},
        "cancer_type_context": "breast",
        "trial_ids": ["NCT02437318"],
    },
    # ── Immunotherapy combinations ────────────────────────────────────────────
    {
        "drugs": ["Nivolumab", "Ipilimumab"],
        "synergy_type": "approved_regimen",
        "synergy_rationale": "PD-1 + CTLA-4 dual checkpoint blockade — complementary mechanisms: PD-1 restores exhausted T cells; CTLA-4 expands T-cell pool in lymph nodes. Synergistic in melanoma and NSCLC.",
        "combination_score": 0.90,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved: melanoma (CheckMate 067), NSCLC TMB-H (CheckMate 227), mesothelioma (CheckMate 743), CRC MSI-H (CheckMate 142).",
        "trigger_genes": set(),
        "trial_ids": ["NCT01844505", "NCT02477826"],
    },
    # ── KRAS G12C + SOS1 ─────────────────────────────────────────────────────
    {
        "drugs": ["Adagrasib", "Cetuximab"],
        "synergy_type": "bypass_resistance",
        "synergy_rationale": "KRAS G12C inhibition causes EGFR-mediated adaptive resistance. Adding anti-EGFR cetuximab suppresses the bypass and improves ORR from ~43% to ~63%.",
        "combination_score": 0.86,
        "evidence_level": "LEVEL_1",
        "evidence_note": "FDA-approved for KRAS G12C CRC (MARIPOSA-2 variant / KRYSTAL-10 NCT04793958). ORR 34% vs 25% single agent.",
        "trigger_genes": {"KRAS"},
        "cancer_type_context": "colorectal",
        "trial_ids": ["NCT04793958"],
    },
]


# ── Scoring engine ─────────────────────────────────────────────────────────────

def score_combinations(
    ranked_drugs: list[dict],
    mutated_genes: Optional[list[str]] = None,
    cancer_type: Optional[str] = None,
    top_n: int = 5,
) -> list[CombinationCandidate]:
    """Find combination therapy candidates from individually-ranked drugs.

    Args:
        ranked_drugs:   Output of rank_candidates() — list of drug dicts with 'drug_name'.
        mutated_genes:  List of mutated gene symbols from the patient. Used to
                        prioritise combinations that target the patient's specific
                        mutation context.
        cancer_type:    Optional cancer type string for context-specific filtering.
        top_n:          Maximum number of combination candidates to return.

    Returns:
        List of CombinationCandidate objects sorted descending by combination_score.
    """
    if not ranked_drugs:
        return []

    # Build lookup sets
    ranked_names_lower = {d.get("drug_name", "").lower() for d in ranked_drugs}
    gene_set: set[str] = {g.upper() for g in (mutated_genes or [])}
    ct_lower = (cancer_type or "").lower()

    results: list[CombinationCandidate] = []

    for combo in _APPROVED_COMBINATIONS:
        drug_names = combo["drugs"]
        # At least one drug must appear in the patient's ranked candidates
        drugs_lower = {d.lower() for d in drug_names}
        if not (drugs_lower & ranked_names_lower):
            continue

        # Check gene trigger relevance
        trigger_genes: set[str] = combo.get("trigger_genes", set())
        gene_relevance = len(trigger_genes & gene_set) / max(len(trigger_genes), 1) if trigger_genes else 0.5

        # Context match
        combo_context = (combo.get("cancer_type_context") or "").lower()
        context_match = (combo_context in ct_lower or ct_lower in combo_context or not combo_context)

        # Penalise combos for the wrong cancer type
        context_score = 1.0 if context_match else 0.6

        final_score = round(combo["combination_score"] * (0.5 + 0.5 * gene_relevance) * context_score, 3)

        results.append(CombinationCandidate(
            drugs=drug_names,
            synergy_type=combo["synergy_type"],
            synergy_rationale=combo["synergy_rationale"],
            combination_score=final_score,
            evidence_level=combo["evidence_level"],
            evidence_note=combo["evidence_note"],
            cancer_type_context=combo.get("cancer_type_context"),
            trial_ids=combo.get("trial_ids", []),
        ))

    # Deduplicate overlapping combos (same drugs different order)
    seen: set[frozenset] = set()
    deduped: list[CombinationCandidate] = []
    for c in sorted(results, key=lambda x: x.combination_score, reverse=True):
        key = frozenset(d.lower() for d in c.drugs)
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    top = deduped[:top_n]
    if top:
        logger.info("[combinations] %d combination candidates for genes %s", len(top), gene_set)
    return top


def combinations_to_summary(combos: list[CombinationCandidate]) -> list[dict]:
    """Serialise combination candidates to JSON-compatible dicts."""
    return [
        {
            "drugs": c.drugs,
            "synergy_type": c.synergy_type,
            "rationale": c.synergy_rationale,
            "combination_score": c.combination_score,
            "evidence_level": c.evidence_level,
            "evidence_note": c.evidence_note,
            "cancer_type_context": c.cancer_type_context,
            "trial_ids": c.trial_ids,
        }
        for c in combos
    ]
