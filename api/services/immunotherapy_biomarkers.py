"""Immunotherapy Biomarker Analysis — OpenOncology

Computes tumour mutational burden (TMB) and microsatellite instability (MSI)
status from the mutation list, then maps those biomarkers to FDA-approved
checkpoint inhibitor indications.

Key biomarkers implemented
──────────────────────────
  TMB-H (≥10 mut/Mb, FDA-approved 2020)
    → Pembrolizumab (KEYNOTE-158, any solid tumour regardless of histology)
  MSI-H / dMMR (microsatellite instability-high / mismatch repair deficient)
    → Pembrolizumab (KEYNOTE-016, pan-tumour FDA approval)
    → Dostarlimab (GARNET trial)
    → Nivolumab + Ipilimumab (CheckMate 142, colorectal)
  PD-L1 proxy scoring
    → Used as soft signal; exact IHC score requires pathology input

References
──────────
  - Marabelle et al., J Clin Oncol 2020 (TMB-H pan-tumour)
  - Le et al., Science 2017 (MSI-H dMMR)
  - FDA approval NDA/BLA database
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# WES effective coding genome size ≈ 38 Mb; WGS ≈ 3000 Mb
# OpenOncology pipeline uses WES by default
WES_CODING_MB: float = 38.0

# FDA TMB-H cut-off: ≥10 mut/Mb (tissue-agnostic)
TMB_HIGH_CUTOFF: float = 10.0
# Borderline zone 7–10 — include as "borderline" signal
TMB_BORDERLINE_CUTOFF: float = 7.0

# MMR gene list — loss-of-function mutations in any imply dMMR/MSI-H
MMR_GENES: frozenset[str] = frozenset({"MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"})

# Homologous recombination deficiency genes — BRCA etc. → PARP inhibitors
HRD_GENES: frozenset[str] = frozenset({
    "BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D",
    "ATM", "BRIP1", "BARD1", "NBN", "RAD50",
})

# POLE/POLD1 ultramutator phenotype → very high TMB → immunotherapy
POLE_GENES: frozenset[str] = frozenset({"POLE", "POLD1"})


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ImmunotherapyProfile:
    """Summary of immunotherapy-relevant biomarkers for one patient."""
    tmb_mutations_per_mb: float
    tmb_status: str              # "TMB-H", "TMB-L", "BORDERLINE"
    msi_status: str              # "MSI-H", "MSS", "UNKNOWN"
    hrd_status: str              # "HRD", "NOT_HRD", "UNKNOWN"
    pole_mutated: bool
    mmr_gene_hits: list[str]     # which MMR genes had mutations
    hrd_gene_hits: list[str]
    raw_mutation_count: int
    genome_mb_denominator: float


@dataclass
class ImmunotherapyCandidate:
    """A checkpoint-inhibitor or immune drug candidate derived from biomarker evidence."""
    drug_name: str
    mechanism: str
    oncokb_level: str            # LEVEL_1 for FDA-approved pan-tumour indications
    approval_status: str
    biomarker_trigger: str       # what biomarker led to this recommendation
    evidence_note: str
    rank_score_estimate: float   # pre-computed score estimate for ranking pipeline
    chembl_id: Optional[str] = None
    evidence_sources: list[str] = field(default_factory=list)


# ── Checkpoint inhibitor catalogue ────────────────────────────────────────────

# TMB-H pan-tumour approved drugs
_TMB_HIGH_DRUGS: list[dict] = [
    {
        "drug_name": "Pembrolizumab",
        "mechanism": "PD-1 checkpoint inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "TMB-H",
        "evidence_note": "FDA-approved for TMB-H ≥10 mut/Mb unresectable/metastatic solid tumours (KEYNOTE-158, 2020)",
        "rank_score_estimate": 0.88,
        "chembl_id": "CHEMBL1418020",
        "evidence_sources": ["FDA_APPROVAL", "KEYNOTE-158"],
    },
]

# MSI-H / dMMR approved drugs
_MSI_HIGH_DRUGS: list[dict] = [
    {
        "drug_name": "Pembrolizumab",
        "mechanism": "PD-1 checkpoint inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "MSI-H/dMMR",
        "evidence_note": "FDA-approved for MSI-H/dMMR unresectable/metastatic solid tumours (KEYNOTE-016/158/164/169/177, 2017 accelerated/2020 regular)",
        "rank_score_estimate": 0.92,
        "chembl_id": "CHEMBL1418020",
        "evidence_sources": ["FDA_APPROVAL", "KEYNOTE-016", "KEYNOTE-177"],
    },
    {
        "drug_name": "Dostarlimab",
        "mechanism": "PD-1 checkpoint inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "MSI-H/dMMR",
        "evidence_note": "FDA-approved for MSI-H/dMMR recurrent/advanced endometrial cancer and other solid tumours (GARNET, 2021)",
        "rank_score_estimate": 0.82,
        "chembl_id": "CHEMBL4523634",
        "evidence_sources": ["FDA_APPROVAL", "GARNET"],
    },
    {
        "drug_name": "Nivolumab",
        "mechanism": "PD-1 checkpoint inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "MSI-H/dMMR",
        "evidence_note": "FDA-approved for MSI-H/dMMR metastatic colorectal cancer (CheckMate 142, 2017)",
        "rank_score_estimate": 0.80,
        "chembl_id": "CHEMBL1827680",
        "evidence_sources": ["FDA_APPROVAL", "CheckMate-142"],
    },
]

# PARP inhibitors for HRD/BRCA-mutant tumours
_HRD_DRUGS: list[dict] = [
    {
        "drug_name": "Olaparib",
        "mechanism": "PARP inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "HRD/BRCA",
        "evidence_note": "FDA-approved for gBRCA-mutated breast/ovarian/prostate/pancreatic cancers; HRD tumours (SOLO1/POLO trials)",
        "rank_score_estimate": 0.90,
        "chembl_id": "CHEMBL521686",
        "evidence_sources": ["FDA_APPROVAL", "SOLO1", "OlympiAD"],
    },
    {
        "drug_name": "Rucaparib",
        "mechanism": "PARP inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "HRD/BRCA",
        "evidence_note": "FDA-approved for gBRCA-mutated ovarian cancer and HRD prostate cancer (ARIEL3/TRITON2)",
        "rank_score_estimate": 0.80,
        "chembl_id": "CHEMBL474328",
        "evidence_sources": ["FDA_APPROVAL", "ARIEL3", "TRITON2"],
    },
    {
        "drug_name": "Niraparib",
        "mechanism": "PARP inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "HRD",
        "evidence_note": "FDA-approved for ovarian/fallopian/peritoneal cancer regardless of BRCA status when HRD-positive (PRIMA/NOVA trials)",
        "rank_score_estimate": 0.78,
        "chembl_id": "CHEMBL3301610",
        "evidence_sources": ["FDA_APPROVAL", "PRIMA", "NOVA"],
    },
    {
        "drug_name": "Talazoparib",
        "mechanism": "PARP inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "HRD/BRCA",
        "evidence_note": "FDA-approved for gBRCA-mutated locally advanced/metastatic HER2-negative breast cancer (EMBRACA trial)",
        "rank_score_estimate": 0.75,
        "chembl_id": "CHEMBL3301622",
        "evidence_sources": ["FDA_APPROVAL", "EMBRACA"],
    },
]

# POLE ultramutator → immunotherapy (very high TMB)
_POLE_DRUGS: list[dict] = [
    {
        "drug_name": "Pembrolizumab",
        "mechanism": "PD-1 checkpoint inhibitor",
        "oncokb_level": "LEVEL_1",
        "approval_status": "Approved",
        "biomarker_trigger": "POLE/POLD1_ultramutator",
        "evidence_note": "POLE/POLD1 exonuclease domain mutations create ultramutator phenotype (>100 mut/Mb). Pembrolizumab approved for TMB-H covers this context; multiple case series support response.",
        "rank_score_estimate": 0.90,
        "chembl_id": "CHEMBL1418020",
        "evidence_sources": ["FDA_APPROVAL", "KEYNOTE-158", "POLE_case_series"],
    },
]


# ── Core functions ─────────────────────────────────────────────────────────────

def compute_immunotherapy_profile(
    mutations: list[dict],
    genome_mb: float = WES_CODING_MB,
) -> ImmunotherapyProfile:
    """Compute TMB, MSI proxy status, HRD, and POLE signals from a mutation list.

    Args:
        mutations: List of mutation dicts from the DB, each with at minimum:
            - gene (str)
            - mutation_type (str)  — e.g. "missense_variant", "frameshift_variant"
        genome_mb: The size in megabases of the sequenced coding region.
            Default: 38 Mb (WES). Use 3000 for WGS.

    Returns:
        ImmunotherapyProfile with all computed biomarker values.
    """
    raw_count = len(mutations)
    tmb_per_mb = raw_count / genome_mb if genome_mb > 0 else 0.0

    if tmb_per_mb >= TMB_HIGH_CUTOFF:
        tmb_status = "TMB-H"
    elif tmb_per_mb >= TMB_BORDERLINE_CUTOFF:
        tmb_status = "BORDERLINE"
    else:
        tmb_status = "TMB-L"

    # MSI proxy: mutations in MMR genes (loss-of-function)
    mmr_hits = [
        m["gene"] for m in mutations
        if m.get("gene", "").upper() in MMR_GENES
        and _is_loss_of_function(m.get("mutation_type", ""))
    ]
    msi_status = "MSI-H" if mmr_hits else ("UNKNOWN" if raw_count < 5 else "MSS")

    # HRD: loss-of-function mutations in HRD genes
    hrd_hits = [
        m["gene"] for m in mutations
        if m.get("gene", "").upper() in HRD_GENES
        and _is_loss_of_function(m.get("mutation_type", ""))
    ]
    hrd_status = "HRD" if hrd_hits else "NOT_HRD"

    # POLE/POLD1 exonuclease domain mutations → ultramutator
    pole_mutated = any(
        m.get("gene", "").upper() in POLE_GENES for m in mutations
    )

    return ImmunotherapyProfile(
        tmb_mutations_per_mb=round(tmb_per_mb, 2),
        tmb_status=tmb_status,
        msi_status=msi_status,
        hrd_status=hrd_status,
        pole_mutated=pole_mutated,
        mmr_gene_hits=list(dict.fromkeys(mmr_hits)),
        hrd_gene_hits=list(dict.fromkeys(hrd_hits)),
        raw_mutation_count=raw_count,
        genome_mb_denominator=genome_mb,
    )


def get_immunotherapy_candidates(
    profile: ImmunotherapyProfile,
    cancer_type: Optional[str] = None,
) -> list[ImmunotherapyCandidate]:
    """Return ranked immunotherapy/PARP-inhibitor candidates based on biomarker profile.

    Candidates are de-duplicated (drug name). The highest rank_score_estimate
    entry wins when duplicates arise from multiple triggers.

    Args:
        profile:     ImmunotherapyProfile from compute_immunotherapy_profile()
        cancer_type: Optional hint to adjust evidence notes (no hard filtering —
                     FDA pan-tumour approvals apply regardless of histology).

    Returns:
        List of ImmunotherapyCandidate objects, sorted descending by rank_score_estimate.
    """
    candidates: dict[str, ImmunotherapyCandidate] = {}

    def _add(drug_dicts: list[dict]) -> None:
        for d in drug_dicts:
            name = d["drug_name"]
            c = ImmunotherapyCandidate(**d)
            if name not in candidates or c.rank_score_estimate > candidates[name].rank_score_estimate:
                candidates[name] = c

    if profile.msi_status == "MSI-H":
        _add(_MSI_HIGH_DRUGS)
        logger.info("[immunotherapy] MSI-H detected (MMR hits: %s) → %d checkpoint candidates",
                    profile.mmr_gene_hits, len(_MSI_HIGH_DRUGS))

    if profile.tmb_status == "TMB-H":
        _add(_TMB_HIGH_DRUGS)
        logger.info("[immunotherapy] TMB-H detected (%.1f mut/Mb) → pembrolizumab candidate",
                    profile.tmb_mutations_per_mb)

    if profile.pole_mutated:
        _add(_POLE_DRUGS)
        logger.info("[immunotherapy] POLE/POLD1 ultramutator detected → immunotherapy boost")

    if profile.hrd_status == "HRD":
        _add(_HRD_DRUGS)
        logger.info("[immunotherapy] HRD detected (genes: %s) → %d PARP inhibitor candidates",
                    profile.hrd_gene_hits, len(_HRD_DRUGS))

    result = sorted(candidates.values(), key=lambda c: c.rank_score_estimate, reverse=True)
    return result


def immunotherapy_candidates_to_drug_dicts(
    candidates: list[ImmunotherapyCandidate],
) -> list[dict]:
    """Convert ImmunotherapyCandidate list to the drug dict format expected by rank_candidates().

    The returned dicts are compatible with DrugScoreComponents so they
    will be ranked alongside mutation-derived candidates.
    """
    return [
        {
            "drug_name": c.drug_name,
            "chembl_id": c.chembl_id,
            "mechanism": c.mechanism,
            "oncokb_level": c.oncokb_level,
            "is_approved": c.approval_status == "Approved",
            "max_phase": 4,
            "rank_score": c.rank_score_estimate,   # pre-estimate; re-ranked by ranking.py
            "binding_score": None,
            "opentargets_score": None,
            "civic_score": None,
            "alphamissense_score": None,
            "evidence_sources": c.evidence_sources + ["immunotherapy_biomarker"],
            "matched_terms": [c.biomarker_trigger, c.mechanism],
        }
        for c in candidates
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

_LOF_TERMS = frozenset({
    "frameshift", "nonsense", "stop_gained", "stop_lost", "splice_acceptor",
    "splice_donor", "splice_region", "frameshift_variant", "stop_gained",
    "transcript_ablation", "start_lost", "loss_of_function",
})


def _is_loss_of_function(mutation_type: str) -> bool:
    """Heuristic: is this mutation likely to cause loss of function?"""
    if not mutation_type:
        return False
    mt = mutation_type.lower()
    return any(term in mt for term in _LOF_TERMS)
