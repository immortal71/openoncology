"""
Drug ranking algorithm for OpenOncology.

Combines scores from multiple independent evidence sources into rank_score [0,1].

All tunable parameters (weights, thresholds, penalty factors) live in
``ranking_config.py``.  The logic here is intentionally parameter-free:
every magic number is read from DEFAULT_CONFIG (or a custom config passed
to the public API functions).

  Source                  Default weight   Notes
  ──────────────────────  ──────────────   ──────────────────────────────────
  DiffDock binding conf.        0.25       Normalised to [0,1] by score.py
  OpenTargets assoc.            0.20       Already [0,1] from API
  OncoKB actionability          0.25       L1=1.0 … L4=0.2, R1=0.10, R2=0.05
  AlphaMissense pathog.         0.10       [0,1] from classifier
  Clinical phase                0.10       approved=1.0, ph3=0.7, ph2=0.5 …
  CIViC evidence                0.10       A=1.0, B=0.8, C=0.6, D=0.4, E=0.2

Evidence-fusion rules applied AFTER the weighted mean:

  1. Source diversity penalty (×config.diversity_penalty.single_source_factor)
     when only ONE source contributes.  A drug known only from OncoKB has
     much wider uncertainty than one confirmed by multiple independent sources.

  2. Resistance hard gate: oncokb_level in config.resistance.levels → score
     is capped at config.resistance.hard_cap.

  3. Safety penalty: config.safety.approved_drug_max_penalty caps how much
     an approved drug can be penalised by the tox/ADME score.

Missing sources are handled by weight redistribution so the total = 1.0.

Each ranked candidate carries:
  - rank_score, rank_score_ci_low, rank_score_ci_high
  - evidence_completeness, confidence_level, missing_sources
  - evidence_audit_trail — per-source breakdown of every contribution
  - score_variance
"""

from __future__ import annotations

import math
from functools import cmp_to_key
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional

from api.ai.ranking_config import DEFAULT_CONFIG, RankingConfig


def _normalize_oncokb_level(level: Optional[str]) -> Optional[str]:
    """Normalize OncoKB levels to canonical tokens (e.g. LEVEL_1, LEVEL_R1)."""
    if level is None:
        return None
    lv = str(level).strip().upper()
    if not lv:
        return None
    aliases = {
        "1": "LEVEL_1",
        "2": "LEVEL_2",
        "3A": "LEVEL_3A",
        "3B": "LEVEL_3B",
        "4": "LEVEL_4",
        "R1": "LEVEL_R1",
        "R2": "LEVEL_R2",
    }
    if lv in aliases:
        return aliases[lv]
    if lv.startswith("LEVEL") and "_" not in lv:
        return lv.replace("LEVEL", "LEVEL_", 1)
    return lv


def _oncokb_score(level: Optional[str], cfg: RankingConfig = DEFAULT_CONFIG) -> Optional[float]:
    normalized = _normalize_oncokb_level(level)
    if not normalized:
        return None
    return cfg.oncokb_scores.as_dict().get(normalized)


def _civic_score_from_level(
    level: Optional[str], cfg: RankingConfig = DEFAULT_CONFIG
) -> Optional[float]:
    """Map CIViC evidence tier (A-E) or pre-computed float to [0,1]."""
    if level is None:
        return None
    if isinstance(level, (int, float)):
        return float(level)
    return cfg.civic_scores.as_dict().get(str(level).upper().strip())


# ── Clinical phase mapping ────────────────────────────────────────────────────

def _phase_score(
    max_phase: Optional[int],
    is_approved: bool = False,
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> Optional[float]:
    if is_approved or max_phase == 4:
        return cfg.phase_scores.approved
    return cfg.phase_scores.for_phase(max_phase)


# ── Main ranking function ─────────────────────────────────────────────────────

@dataclass
class DrugScoreComponents:
    binding_score: Optional[float] = None        # DiffDock [0,1]
    opentargets_score: Optional[float] = None    # OpenTargets [0,1]
    oncokb_level: Optional[str] = None           # e.g. "LEVEL_1"
    alphamissense_score: Optional[float] = None  # AlphaMissense [0,1]
    max_phase: Optional[int] = None              # clinical trial phase
    is_approved: bool = False
    civic_score: Optional[float] = None          # CIViC tier score [0,1]
    oncokb_weight_multiplier: float = 1.0        # down-weight gene-level fallback matches
    safety_score_penalty: float = 0.0            # subtracted penalty from tox/ADME gate
    co_mutation_penalty: float = 0.0             # penalty from competing pathway co-mutations
    vaf: Optional[float] = None                  # variant allele frequency [0,1]


_RESISTANCE_NEXT_LINE_BY_GENE: dict[str, tuple[str, ...]] = {
    "EGFR": ("osimertinib", "amivantamab", "lazertinib", "mobocertinib"),
    "ALK": ("lorlatinib", "brigatinib", "alectinib"),
    "ROS1": ("repotrectinib", "lorlatinib", "entrectinib"),
    "RET": ("selpercatinib", "pralsetinib", "cabozantinib"),
    "MET": ("tepotinib", "capmatinib"),
    "BRAF": ("dabrafenib", "trametinib", "encorafenib", "binimetinib"),
    "KRAS": ("adagrasib", "sotorasib"),
    "FLT3": ("gilteritinib", "quizartinib"),
    "ABL1": ("ponatinib", "asciminib", "bosutinib"),
    "KIT": ("avapritinib", "ripretinib", "regorafenib"),
    "PDGFRA": ("avapritinib", "sunitinib"),
    "BTK": ("pirtobrutinib", "venetoclax"),
    "ESR1": ("elacestrant",),
    "ERBB2": ("trastuzumab deruxtecan", "tucatinib", "neratinib"),
    "NTRK1": ("larotrectinib", "entrectinib"),
    "NTRK2": ("larotrectinib", "entrectinib"),
    "NTRK3": ("larotrectinib", "entrectinib"),
    "PIK3CA": ("alpelisib", "capivasertib"),
    "IDH1": ("ivosidenib", "olutasidenib", "vorasidenib"),
    "IDH2": ("enasidenib",),
}

_RESISTANCE_NEXT_LINE_BY_VARIANT: dict[tuple[str, str], tuple[str, ...]] = {
    ("EGFR", "T790M"): ("osimertinib",),
    ("EGFR", "C797S"): ("amivantamab", "lazertinib"),
    ("ALK", "G1202R"): ("lorlatinib",),
    ("ROS1", "G2032R"): ("repotrectinib", "lorlatinib"),
    ("ABL1", "T315I"): ("ponatinib", "asciminib"),
    ("FLT3", "D835Y"): ("gilteritinib",),
    ("KIT", "D816V"): ("avapritinib",),
    ("PDGFRA", "D842V"): ("avapritinib",),
    ("BTK", "C481S"): ("pirtobrutinib",),
    ("ESR1", "Y537S"): ("elacestrant",),
}


# ── Drug tier classification ──────────────────────────────────────────────────

def classify_drug_tier(
    oncokb_level: Optional[str],
    is_approved: bool,
    max_phase: Optional[int],
    approval_status: Optional[str] = None,
) -> str:
    """Classify a drug candidate into an explicit tier label.

    Tiers (in priority order):
      fda_approved        — OncoKB Level 1/2 + drug is FDA-approved
      repurposed          — FDA-approved for *different* indication; no L1/L2
      investigational_late  — Phase 3 trial, not yet approved
      investigational_early — Phase 1 or 2 trial
      preclinical         — No human trial data

    The result is stored as ``drug_tier`` on each ranked candidate and is
    returned in every API response so the frontend can display the correct
    badge without re-deriving the logic.
    """
    level = _normalize_oncokb_level(oncokb_level) or ""

    # Resistance-annotated drugs — never display as actionable tier
    if level in {"LEVEL_R1", "LEVEL_R2"}:
        return "resistance_mechanism"

    # Tier 1: FDA-approved for this specific variant + cancer type
    if level in {"LEVEL_1", "LEVEL_2"} and is_approved:
        return "fda_approved"

    # Tier 1 edge case: Level 1/2 evidence but approval status unknown
    if level in {"LEVEL_1", "LEVEL_2"}:
        return "fda_approved"

    # Tier 2: Approved drug with weaker evidence (Level 3/4 or off-label)
    _approval_str = (approval_status or "").lower()
    if is_approved or "approved" in _approval_str:
        return "repurposed"

    # Tier 3: Investigational
    _phase = max_phase or 0
    if _phase >= 3:
        return "investigational_late"
    if _phase >= 1:
        return "investigational_early"

    return "preclinical"


def _decision_path(tiers_present: list[str]) -> str:
    """Return a decision_path string based on which tiers have candidates."""
    if "fda_approved" in tiers_present:
        return "tier1_found"
    if "repurposed" in tiers_present:
        return "tier2_only"
    if "investigational_late" in tiers_present or "investigational_early" in tiers_present:
        return "tier3_escalation"
    return "abstain"


def _resistance_next_line_boost(
    candidate: dict,
    resistance_context: Optional[dict],
) -> tuple[float, str]:
    if not resistance_context:
        return 0.0, ""

    level = _normalize_oncokb_level(str(resistance_context.get("level") or ""))
    if level not in {"LEVEL_R1", "LEVEL_R2"}:
        return 0.0, ""

    gene = str(resistance_context.get("gene") or "").upper().strip()
    variant = str(resistance_context.get("variant") or "").upper().strip()
    drug_name = str(candidate.get("drug_name") or candidate.get("name") or "").lower()
    if not gene or not drug_name:
        return 0.0, ""

    match_variant = _RESISTANCE_NEXT_LINE_BY_VARIANT.get((gene, variant), ())
    match_gene = _RESISTANCE_NEXT_LINE_BY_GENE.get(gene, ())

    # Never boost a resistance-annotated drug.
    cand_level = _normalize_oncokb_level(candidate.get("oncokb_level"))
    if cand_level in {"LEVEL_R1", "LEVEL_R2"}:
        return 0.0, ""

    if any(tok in drug_name for tok in match_variant):
        return 0.15, f"resistance_next_line_variant:{gene} {variant}"
    if any(tok in drug_name for tok in match_gene):
        return 0.10, f"resistance_next_line_gene:{gene}"
    return 0.0, ""


def compute_rank_score(
    components: DrugScoreComponents,
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> float:
    """Return a rank_score in [0, 1] fusing all available evidence sources.

    Three post-mean adjustments (all thresholds read from cfg):
      ① Source diversity penalty when only one source contributes.
      ② Resistance hard gate caps score for LEVEL_R1/R2 drugs.
      ③ Safety penalty subtracted; capped for approved drugs.

    Pass a custom ``cfg`` to run ablation studies (e.g., zero out one source's
    weight) without touching this function.
    """
    w = cfg.weights
    raw: list[tuple[Optional[float], float]] = [
        (components.binding_score,                                       w.binding),
        (components.opentargets_score,                                   w.opentargets),
        (
            _oncokb_score(components.oncokb_level, cfg),
            w.oncokb * max(min(float(components.oncokb_weight_multiplier), 1.0), 0.0),
        ),
        (components.alphamissense_score,                                 w.alphamissense),
        (_phase_score(components.max_phase, components.is_approved, cfg), w.clinical_phase),
        (_civic_score_from_level(components.civic_score, cfg),           w.civic),
    ]

    available = [(score, weight) for score, weight in raw if score is not None]
    if not available:
        return 0.0

    total_weight = sum(wt for _, wt in available)
    if total_weight == 0:
        return 0.0

    rank = sum(score * (weight / total_weight) for score, weight in available)
    source_scores = [score for score, _ in available]

    # ① Source diversity penalty: single-source conclusions are less reliable.
    if len(available) == 1:
        rank *= cfg.diversity_penalty.single_source_factor

    # ① High-evidence floor: L1/L2 drugs must rank above unvalidated candidates
    # regardless of which other sources happen to be absent in offline mode.
    # Applied BEFORE the resistance gate so the gate can still cap R1/R2 drugs.
    _floor_map = {
        "LEVEL_1": cfg.high_evidence_floor.l1_min_score,
        "LEVEL_2": cfg.high_evidence_floor.l2_min_score,
    }
    _level_str = _normalize_oncokb_level(components.oncokb_level) or ""
    _floor = _floor_map.get(_level_str)
    if _floor is not None:
        rank = max(rank, _floor)

    # ② Resistance hard gate: resistance-annotated drugs must rank at the bottom.
    if _level_str and _level_str in cfg.resistance.levels:
        rank = min(rank, cfg.resistance.hard_cap)

    # ③ Safety penalty (capped for approved drugs whose profile is clinically known).
    penalty = components.safety_score_penalty
    if components.is_approved:
        penalty = min(penalty, cfg.safety.approved_drug_max_penalty)
    rank = max(rank - penalty, 0.0)

    # ④ Co-mutation penalty: competing pathway mutations may reduce drug efficacy.
    # Unlike safety penalty, this is NOT capped for approved drugs — the
    # biological rationale applies regardless of approval status.
    rank = max(rank - components.co_mutation_penalty, 0.0)

    # ⑤ Very low VAF score discount: subclonal mutations may not be the dominant
    # driver, reducing the expected benefit of drugs targeting that mutation.
    if (components.vaf is not None
            and components.vaf < cfg.low_vaf.very_low_vaf_threshold):
        rank = max(rank - cfg.low_vaf.very_low_vaf_score_discount, 0.0)

    # ⑥ Robustness scoring: reward convergent evidence, penalize conflict.
    # L1/L2 drugs are exempt from the variance penalty: their clinical evidence
    # is authoritative. Disagreement from structural scores (DiffDock) or
    # broad-association scores (OpenTargets) is expected for drugs whose
    # mechanism doesn't rely on direct kinase binding (immunotherapy, PARPi,
    # CDK4/6i). Penalising them here causes CONFLICTING_EVIDENCE misranking.
    rb = cfg.robustness
    _high_evidence = _level_str in {"LEVEL_1", "LEVEL_2"}
    if len(source_scores) >= 2 and not _high_evidence:
        mean_s = sum(source_scores) / len(source_scores)
        variance = sum((s - mean_s) ** 2 for s in source_scores) / len(source_scores)
        conflict_penalty = min(variance * rb.variance_penalty_factor, rb.max_variance_penalty)
        rank = max(rank - conflict_penalty, 0.0)

    oncokb = _oncokb_score(components.oncokb_level, cfg)
    civic = _civic_score_from_level(components.civic_score, cfg)
    if oncokb is not None and civic is not None and _level_str not in cfg.resistance.levels:
        translational_bonus = min(min(oncokb, civic) * rb.translational_bonus_factor, rb.max_translational_bonus)
        rank = min(rank + translational_bonus, 1.0)

    if len(available) >= 2:
        support_bonus = min(
            (len(available) - 1) * rb.multi_source_bonus_per_source,
            rb.multi_source_bonus_cap,
        )
        rank = min(rank + support_bonus, 1.0)

    # Keep high-evidence floors intact after robustness shaping.
    if _floor is not None and _level_str not in cfg.resistance.levels:
        rank = max(rank, _floor)

    return round(min(rank, 1.0), 4)


def compute_uncertainty(
    components: DrugScoreComponents,
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> dict:
    """Compute confidence interval, evidence completeness, and per-source audit trail.

    Two uncertainty components:
      1. Epistemic (missing data): each absent source adds to CI half-width.
      2. Aleatoric (source disagreement): variance across available scores.

    Returns dict with keys:
      rank_score_ci_low, rank_score_ci_high, evidence_completeness,
      confidence_level, missing_sources, score_variance, evidence_audit_trail
    """
    w = cfg.weights
    uc = cfg.uncertainty
    raw: list[tuple[Optional[float], float, str]] = [
        (components.binding_score,                                        w.binding,        "DiffDock"),
        (components.opentargets_score,                                    w.opentargets,    "OpenTargets"),
        (
            _oncokb_score(components.oncokb_level, cfg),
            w.oncokb * max(min(float(components.oncokb_weight_multiplier), 1.0), 0.0),
            "OncoKB",
        ),
        (components.alphamissense_score,                                  w.alphamissense,  "AlphaMissense"),
        (_phase_score(components.max_phase, components.is_approved, cfg), w.clinical_phase, "ClinicalPhase"),
        (_civic_score_from_level(components.civic_score, cfg),            w.civic,          "CIViC"),
    ]

    available_scores = [s for s, _, _ in raw if s is not None]
    missing_sources = [name for s, _, name in raw if s is None]
    n_total = len(raw)
    n_available = len(available_scores)

    evidence_completeness = round(n_available / n_total, 2)

    # Epistemic uncertainty: each missing source widens the CI
    epistemic_hw = len(missing_sources) * uc.epistemic_hw_per_missing_source

    # Aleatoric uncertainty: variance among available scores
    score_variance = 0.0
    if len(available_scores) >= 2:
        mean_s = sum(available_scores) / len(available_scores)
        score_variance = sum((s - mean_s) ** 2 for s in available_scores) / len(available_scores)
        aleatoric_hw = math.sqrt(score_variance) * 0.5
    else:
        aleatoric_hw = uc.single_source_aleatoric_hw

    half_width = round(min(epistemic_hw + aleatoric_hw, uc.max_half_width), 3)

    # VAF-based CI boost: low allele fraction → wider uncertainty
    vaf_boost = 0.0
    if components.vaf is not None:
        vaf_cfg = cfg.low_vaf
        if components.vaf < vaf_cfg.very_low_vaf_threshold:
            vaf_boost = vaf_cfg.very_low_vaf_ci_boost
        elif components.vaf < vaf_cfg.low_vaf_threshold:
            vaf_boost = vaf_cfg.low_vaf_ci_boost
    half_width = round(min(half_width + vaf_boost, uc.max_half_width), 3)

    point = compute_rank_score(components, cfg)
    ci_low = round(max(point - half_width, 0.0), 4)
    ci_high = round(min(point + half_width, 1.0), 4)

    if evidence_completeness >= uc.high_confidence_threshold:
        confidence_level = "HIGH"
    elif evidence_completeness >= uc.medium_confidence_threshold:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    # Per-source audit trail
    total_available_weight = sum(wt for s, wt, _ in raw if s is not None) or 1.0
    evidence_audit_trail = [
        {
            "source": name,
            "raw_score": round(s, 4) if s is not None else None,
            "nominal_weight": wt,
            "effective_weight": round(wt / total_available_weight, 4) if s is not None else 0.0,
            "contributed": s is not None,
        }
        for s, wt, name in raw
    ]

    return {
        "rank_score_ci_low": ci_low,
        "rank_score_ci_high": ci_high,
        "evidence_completeness": evidence_completeness,
        "confidence_level": confidence_level,
        "missing_sources": missing_sources,
        "score_variance": round(score_variance, 4),
        "evidence_audit_trail": evidence_audit_trail,
    }


def rank_candidates(
    candidates: list[dict],
    resistance_context: Optional[dict] = None,
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> list[dict]:
    """Compute rank_score (with full evidence audit) for each candidate and sort.

    Expected keys per candidate (all optional):
      binding_score, opentargets_score, oncokb_level, alphamissense_score,
      max_phase, is_approved, civic_score, safety_score_penalty,
      chembl_id, drug_name, mechanism, action_type

    Added keys per candidate:
      rank_score, rank_score_ci_low, rank_score_ci_high,
      evidence_completeness, confidence_level, missing_sources,
      evidence_audit_trail, score_variance

    Pass a custom ``cfg`` to run ablation studies — the same candidate list
    will be scored under different weight assumptions.
    """
    for c in candidates:
        if resistance_context is None:
            inferred_level = _normalize_oncokb_level(c.get("oncokb_level"))
            if inferred_level in {"LEVEL_R1", "LEVEL_R2"}:
                inferred_gene = (c.get("target_gene") or c.get("gene") or "").upper()
                inferred_variant = str(c.get("protein_change") or c.get("variant") or "").upper()
                resistance_context = {
                    "gene": inferred_gene,
                    "variant": inferred_variant,
                    "level": inferred_level,
                }

        if c.get("co_mutation_penalty") is None and c.get("co_mutated_genes"):
            gene = c.get("target_gene") or c.get("gene") or ""
            c["co_mutation_penalty"] = compute_co_mutation_penalty(
                gene,
                c.get("co_mutated_genes") or [],
                cfg,
            )

        # For candidates coming from DGIdb, blend the dgidb_score into
        # opentargets_score (take the max so we never penalize by averaging).
        dgidb_score = c.get("dgidb_score")
        if dgidb_score is not None:
            existing_ot = c.get("opentargets_score")
            if existing_ot is None:
                c["opentargets_score"] = float(dgidb_score)
            else:
                c["opentargets_score"] = max(float(existing_ot), float(dgidb_score))

        # Trusted multi-source bonus: if a candidate is supported by 3+ trusted
        # databases (e.g. OpenTargets + DGIdb + CIViC), boost opentargets_score
        # slightly to reflect convergent evidence.
        trusted_count = int(c.get("trusted_source_count") or 0)
        if trusted_count >= 3 and c.get("opentargets_score") is not None:
            bonus = min((trusted_count - 2) * 0.03, 0.10)
            c["opentargets_score"] = min(float(c["opentargets_score"]) + bonus, 1.0)

        components = DrugScoreComponents(
            binding_score=c.get("binding_score"),
            opentargets_score=c.get("opentargets_score"),
            oncokb_level=c.get("oncokb_level"),
            alphamissense_score=c.get("alphamissense_score"),
            oncokb_weight_multiplier=(
                0.5
                if bool(c.get("oncokb_gene_fallback"))
                and _normalize_oncokb_level(c.get("oncokb_level")) not in {"LEVEL_R1", "LEVEL_R2"}
                else 1.0
            ),
            max_phase=c.get("max_phase") or c.get("phase"),
            is_approved=bool(c.get("is_approved")),
            civic_score=c.get("civic_score"),
            safety_score_penalty=float(c.get("safety_score_penalty") or 0.0),
            co_mutation_penalty=float(c.get("co_mutation_penalty") or 0.0),
            vaf=c.get("vaf"),
        )
        c["rank_score"] = compute_rank_score(components, cfg)
        c.update(compute_uncertainty(components, cfg))

        # Drug tier classification — explicit tier for UI display and API consumers
        c["drug_tier"] = classify_drug_tier(
            oncokb_level=c.get("oncokb_level"),
            is_approved=bool(c.get("is_approved")),
            max_phase=c.get("max_phase") or c.get("phase"),
            approval_status=c.get("approval_status"),
        )

        boost, rationale = _clinical_priority_boost(c, cfg)
        c["clinical_priority_boost"] = boost
        c["clinical_priority_rationale"] = rationale

        resistance_boost, resistance_rationale = _resistance_next_line_boost(c, resistance_context)
        c["resistance_context_boost"] = resistance_boost
        c["resistance_context_rationale"] = resistance_rationale

    def _rank_compare(a: dict, b: dict) -> int:
        score_a = float(a.get("rank_score") or 0.0)
        score_b = float(b.get("rank_score") or 0.0)
        window = max(float(cfg.clinical_priority.tie_score_window), 0.0)
        if abs(score_a - score_b) > window:
            return -1 if score_a > score_b else 1

        key_a = _tiebreaker_key(a, cfg)
        key_b = _tiebreaker_key(b, cfg)
        if key_a < key_b:
            return -1
        if key_a > key_b:
            return 1
        return 0

    sorted_candidates = sorted(candidates, key=cmp_to_key(_rank_compare))

    # Attach a decision_path to every candidate so callers can see the
    # overall conclusion without inspecting every drug_tier individually.
    tiers_present = [c.get("drug_tier", "preclinical") for c in sorted_candidates]
    path = _decision_path(tiers_present)
    for c in sorted_candidates:
        c["decision_path"] = path

    return sorted_candidates


def _tiebreaker_key(c: dict, cfg: RankingConfig = DEFAULT_CONFIG) -> tuple:
    level = _normalize_oncokb_level(c.get("oncokb_level")) or ""
    oncokb_s = _oncokb_score(level, cfg) or 0.0
    civic_s = _civic_score_from_level(c.get("civic_score"), cfg) or 0.0
    phase_s = _phase_score(c.get("max_phase") or c.get("phase"), bool(c.get("is_approved")), cfg) or 0.0
    clinical_priority_boost = float(c.get("clinical_priority_boost") or 0.0)
    resistance_context_boost = float(c.get("resistance_context_boost") or 0.0)
    is_resistant = "R" in level and level.startswith("LEVEL_")
    has_positive = level.startswith("LEVEL_") and not is_resistant
    return (
        -(float(c.get("rank_score") or 0.0) + clinical_priority_boost + resistance_context_boost),
        2 if is_resistant else (0 if has_positive else 1),
        -oncokb_s,
        -resistance_context_boost,
        -clinical_priority_boost,
        -civic_s,
        -phase_s,
        -float(c.get("evidence_completeness") or 0.0),
        str(c.get("drug_name") or ""),
    )


def _clinical_priority_boost(
    candidate: dict,
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> tuple[float, str]:
    cp_cfg = cfg.clinical_priority
    if not cp_cfg.enabled:
        return 0.0, "disabled"

    level = _normalize_oncokb_level(candidate.get("oncokb_level")) or ""
    name = str(candidate.get("drug_name") or candidate.get("name") or "").lower()
    if not level or not name:
        return 0.0, ""

    context = " ".join(
        str(candidate.get(k) or "")
        for k in (
            "gene",
            "target_gene",
            "target",
            "cancer_type",
            "tumor_type",
            "indication",
            "case_id",
        )
    ).lower()

    applied: list[str] = []
    total_boost = 0.0
    for rule in cp_cfg.rules:
        if level not in rule.oncokb_levels:
            continue
        if rule.drug_contains.lower() not in name:
            continue
        if rule.gene_contains and rule.gene_contains.lower() not in context:
            continue
        if rule.cancer_contains and rule.cancer_contains.lower() not in context:
            continue
        total_boost += max(rule.boost, 0.0)
        applied.append(rule.rationale)

    total_boost = min(total_boost, max(cp_cfg.max_total_boost, 0.0))
    if total_boost <= 0.0:
        return 0.0, ""
    return round(total_boost, 4), "; ".join(applied)


# ── System limitations summary ────────────────────────────────────────────────

SYSTEM_LIMITATIONS: list[str] = [
    "Ranking scores are statistical estimates, NOT clinical recommendations.",
    "OncoKB / CIViC annotations depend on database currency; newly approved "
    "therapies may not yet appear in evidence tables.",
    "DiffDock binding scores are structural predictions without experimental "
    "validation; predicted binding does not imply in-vivo efficacy.",
    "AlphaMissense pathogenicity scores cover single amino-acid changes only; "
    "indels, fusions, and CNVs use separate evidence pathways.",
    "Toxicity / ADME predictions are QSAR estimates (structural alerts + "
    "physicochemical heuristics). Mandatory wet-lab confirmation before IND: "
    "Ames OECD TG 471, hERG patch-clamp IQ-CSRC protocol, HLM stability assay.",
    f"Source diversity penalty (×{DEFAULT_CONFIG.diversity_penalty.single_source_factor}) "
    "is applied when only one evidence source contributes; these rankings have "
    "wider CIs and lower reliability.",
    f"Resistance hard gate caps rank_score at {DEFAULT_CONFIG.resistance.hard_cap} for "
    "LEVEL_R1/R2; this relies on the curated table for offline use — always verify "
    "via the live OncoKB API.",
    "Injected drugs (absent from OpenTargets query results) have opentargets_score=None "
    "and are scored on OncoKB / phase evidence only.",
    "Benchmark validated on ~200 gold-standard cases (OncoKB L1/L2 + CIViC Tier A); "
    "performance on VUS, low-purity samples, complex co-mutations, and rare cancers "
    "is not yet well characterised.",
    "Co-mutations, subclonal architecture, tumour heterogeneity, and acquired "
    "resistance mechanisms are not fully modelled.",
    "Evidence weights are research defaults — see ranking_config.py. No formal "
    "optimisation against real-world outcome data has been performed.",
    "AlphaFold structure prediction and DiffDock docking are NOT run in the default "
    "demo; binding_score is absent unless the optional AI pipeline is configured.",
]


def get_system_limitations(cfg: RankingConfig = DEFAULT_CONFIG) -> dict:
    """Return the system limitations as a structured dict for inclusion in reports."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": (
            "FOR RESEARCH USE ONLY. Not for clinical decision-making. "
            "Always consult a board-certified oncologist."
        ),
        "limitations": SYSTEM_LIMITATIONS,
        "active_config": cfg.describe(),
    }


# ── Co-mutation utilities ─────────────────────────────────────────────────────

def compute_co_mutation_penalty(
    target_gene: str,
    co_mutated_genes: list[str],
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> float:
    """Compute the co-mutation pathway-conflict penalty for a drug targeting target_gene.

    Returns a float penalty [0, max_co_mutation_penalty] to subtract from the
    rank score of any drug whose primary target is ``target_gene``.

    A penalty is incurred when:
      - ``target_gene`` belongs to a pathway group in cfg.co_mutation.pathway_groups
      - One or more ``co_mutated_genes`` ALSO belong to that group
      - The co-mutation could compensate for (or compete with) the drug's mechanism

    Example: EGFR + KRAS co-mutation.  KRAS is in the RAS/MAPK group, as is BRAF.
    A drug targeting EGFR would still be partially blocked by the downstream KRAS
    activation.  The penalty applies to the EGFR drug but NOT to a KRAS-directed drug.
    """
    if not co_mutated_genes:
        return 0.0

    cm_cfg = cfg.co_mutation
    target_upper = target_gene.upper()
    co_upper = {g.upper() for g in co_mutated_genes if g}

    total_penalty = 0.0
    for group in cm_cfg.pathway_groups:
        if target_upper not in group:
            continue
        # Count co-mutations that are in the SAME pathway group (competitors/compensators)
        competing_hits = len(co_upper & group - {target_upper})
        total_penalty += competing_hits * cm_cfg.competing_pathway_penalty

    return round(min(total_penalty, cm_cfg.max_co_mutation_penalty), 4)


def apply_co_mutation_penalties(
    candidates: list[dict],
    co_mutated_genes: list[str],
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> list[dict]:
    """Attach co_mutation_penalty to each candidate based on its target gene.

    Should be called BEFORE rank_candidates() to ensure the penalty is
    incorporated into the rank_score calculation.

    Args:
        candidates:        List of candidate dicts (each may have ``target_gene``).
        co_mutated_genes:  List of genes that are also mutated in this patient
                           (excluding the primary target gene).
        cfg:               Ranking configuration.

    Returns:
        Same list with ``co_mutation_penalty`` set on each candidate.
    """
    for c in candidates:
        gene = c.get("target_gene") or c.get("gene") or ""
        penalty = compute_co_mutation_penalty(gene, co_mutated_genes, cfg)
        c["co_mutation_penalty"] = penalty
    return candidates


# ── No-strong-candidate detection ────────────────────────────────────────────

def detect_no_strong_candidate(
    ranked_candidates: list[dict],
    cfg: RankingConfig = DEFAULT_CONFIG,
) -> dict:
    """Detect whether the top ranked candidate is strong enough to be actionable.

    Returns a dict with keys:
      - status: "no_candidate" | "weak" | "moderate" | "strong"
      - top_score: float — rank_score of the best non-resistance candidate
      - message: str — human-readable verdict for inclusion in reports
      - actionable: bool — False when no clinically actionable drug exists

    This function is a guard against silently presenting a rank_score of 0.18
    as if it were a useful recommendation.  When status is "no_candidate", the
    report should prominently state that no standard-of-care targeted therapy
    was identified and recommend alternative pathways (clinical trial enrolment,
    broad immune checkpoint, tumour board review).
    """
    sensitivity_candidates = [
        c for c in ranked_candidates
        if (c.get("oncokb_level") or "").upper() not in ("LEVEL_R1", "LEVEL_R2")
        and not c.get("is_denovo")
    ]

    if not sensitivity_candidates:
        return {
            "status": "no_candidate",
            "top_score": 0.0,
            "actionable": False,
            "message": (
                "No therapeutic candidates were identified for this mutation profile. "
                "No OncoKB Level 1–4 or CIViC evidence-matched drugs appear in the "
                "current query.  Recommendation: (1) Review mutation classification — "
                "the variant may be a passenger or VUS; (2) Consider broad immunotherapy "
                "if TMB/MSI status supports it; (3) Enrol in a tumour-agnostic basket "
                "trial; (4) Discuss at molecular tumour board."
            ),
        }

    top_score = sensitivity_candidates[0].get("rank_score") or 0.0
    nd_cfg = cfg.no_drug

    if top_score <= nd_cfg.no_drug_threshold:
        return {
            "status": "no_candidate",
            "top_score": top_score,
            "actionable": False,
            "message": (
                f"The highest-ranked therapeutic candidate has a rank score of "
                f"{top_score:.2f} (threshold for actionability: "
                f"{nd_cfg.no_drug_threshold:.2f}). This score reflects weak or "
                f"conflicting evidence across all data sources.  This mutation profile "
                f"is NOT currently actionable with a strong therapeutic option. "
                f"Consider: clinical trial enrolment, immunotherapy if biomarkers support "
                f"it, or watchful waiting pending further evidence."
            ),
        }
    elif top_score <= nd_cfg.warn_threshold:
        top_drug = sensitivity_candidates[0].get("drug_name", "top candidate")
        return {
            "status": "weak",
            "top_score": top_score,
            "actionable": False,
            "message": (
                f"The top-ranked candidate ({top_drug}, score {top_score:.2f}) has "
                f"weak evidence support. The analysis suggests a possible therapeutic "
                f"direction, but the signal is below the actionability threshold of "
                f"{nd_cfg.warn_threshold:.2f}. Recommendations are exploratory only and "
                f"require molecular tumour board review before any clinical use."
            ),
        }
    else:
        top_drug = sensitivity_candidates[0].get("drug_name", "top candidate")
        return {
            "status": "strong" if top_score >= 0.6 else "moderate",
            "top_score": top_score,
            "actionable": True,
            "message": (
                f"Actionable therapeutic options identified (top: {top_drug}, "
                f"score {top_score:.2f}). See Section 4 for ranked recommendations."
            ),
        }
