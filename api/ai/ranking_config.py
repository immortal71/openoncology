"""Ranking configuration — all tunable parameters in one place.

Edit this file (or construct a custom RankingConfig) to adjust scoring
behaviour without touching ranking.py logic.

Moving every magic number here makes it easy for:
  - Contributors to understand weight choices and submit pull requests
    with evidence-backed parameter changes.
  - Ablation studies: swap DEFAULT_CONFIG for a variant that zeros out
    one source to measure its marginal contribution.
  - Future A/B tests comparing two weight sets side-by-side.

IMPORTANT: EvidenceWeights nominal values must sum to 1.0.  Call
RankingConfig.validate() after constructing a custom instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Evidence source weights
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvidenceWeights:
    """Nominal weights for each evidence source.

    When a source is unavailable its weight is redistributed proportionally
    across the remaining sources (see ranking.py for the redistribution logic).
    These values therefore represent the *intended* share of the score, not a
    guarantee — the effective weight depends on source availability.

        Rationale:
            - OncoKB (0.40) is the strongest variant-specific clinical signal and
                therefore carries the largest share.
            - DiffDock (0.15) is useful when present but optional in most runs, so
                it should not dominate ranking behavior.
            - OpenTargets (0.15) provides broad target-disease evidence across many
                data types but is less variant-specific than OncoKB.
      - CIViC (0.10) and Clinical Phase (0.10) each add independent lines of
        evidence at lower weight due to smaller coverage.
      - AlphaMissense (0.10) is the weakest predictor of drug sensitivity —
        pathogenicity ≠ druggability — so it carries the smallest weight.

    References for weight choices:
      - Tamborero et al., Cancer Cell 2018 — multi-source evidence integration
      - Suehnholz et al., Cancer Discov. 2023 — OncoKB precision oncology
    """
    binding: float = 0.15          # DiffDock structural binding confidence [0,1]
    opentargets: float = 0.15      # OpenTargets target-disease association [0,1]
    oncokb: float = 0.40           # OncoKB actionability level (mapped to score)
    alphamissense: float = 0.10    # AlphaMissense pathogenicity [0,1]
    clinical_phase: float = 0.10   # Highest clinical trial phase / approval status
    civic: float = 0.10            # CIViC evidence tier (A–E mapped to score)

    def validate(self) -> None:
        """Raise ValueError if weights do not sum to 1.0 (within float tolerance)."""
        total = (self.binding + self.opentargets + self.oncokb
                 + self.alphamissense + self.clinical_phase + self.civic)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"EvidenceWeights must sum to 1.0 — got {total:.6f}. "
                "Adjust individual weights so they sum to exactly 1."
            )

    def as_ordered_list(self) -> list[tuple[str, float]]:
        """Return (source_name, weight) pairs in the canonical source order."""
        return [
            ("DiffDock", self.binding),
            ("OpenTargets", self.opentargets),
            ("OncoKB", self.oncokb),
            ("AlphaMissense", self.alphamissense),
            ("ClinicalPhase", self.clinical_phase),
            ("CIViC", self.civic),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# OncoKB level → score mapping
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OncoKBScores:
    """OncoKB actionability level → numerical score mapping.

    Sensitivity levels (L1–L4) reflect clinical evidence strength from
    the FDA-approved biomarker (L1) down to pre-clinical evidence (L4).
    Resistance levels (R1–R2) are kept LOW intentionally — their primary
    role is to trigger the resistance hard gate, not to contribute positively
    to the rank score.
    """
    LEVEL_1:  float = 1.00   # FDA-approved, same tumour type
    LEVEL_2:  float = 0.80   # Standard-of-care or FDA-approved other tumour type
    LEVEL_3A: float = 0.60   # Compelling clinical evidence
    LEVEL_3B: float = 0.40   # Standard-of-care or investigational in other context
    LEVEL_4:  float = 0.20   # Biological evidence only (pre-clinical)
    LEVEL_R1: float = 0.10   # Standard-of-care resistance
    LEVEL_R2: float = 0.05   # Investigational resistance

    def as_dict(self) -> dict[str, float]:
        return {
            "LEVEL_1":  self.LEVEL_1,
            "LEVEL_2":  self.LEVEL_2,
            "LEVEL_3A": self.LEVEL_3A,
            "LEVEL_3B": self.LEVEL_3B,
            "LEVEL_4":  self.LEVEL_4,
            "LEVEL_R1": self.LEVEL_R1,
            "LEVEL_R2": self.LEVEL_R2,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CIViC evidence tier → score mapping
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CIViCScores:
    """CIViC evidence tier (A–E) → score.

    Tier A = validated in prospective RCT or large retrospective multi-site;
    Tier E = inferential or in silico only.
    """
    A: float = 1.00
    B: float = 0.80
    C: float = 0.60
    D: float = 0.40
    E: float = 0.20

    def as_dict(self) -> dict[str, float]:
        return {"A": self.A, "B": self.B, "C": self.C, "D": self.D, "E": self.E}


# ─────────────────────────────────────────────────────────────────────────────
# Clinical phase → score mapping
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PhaseScores:
    """Clinical trial phase → score.

    An FDA-approved drug (is_approved=True) or phase 4 trial gets max score.
    Phase 0 and unknown phases get a small but nonzero score to avoid
    completely discarding structurally attractive early-phase candidates.
    """
    approved: float = 1.00   # is_approved=True or max_phase ≥ 4
    phase_3:  float = 0.70
    phase_2:  float = 0.50
    phase_1:  float = 0.30
    phase_0:  float = 0.10
    unknown:  float = 0.10   # phase provided but not in the known set

    def for_phase(self, phase: Optional[int]) -> Optional[float]:
        """Map an integer phase to a score, returning None for missing data."""
        if phase is None:
            return None
        mapping = {
            4: self.approved,
            3: self.phase_3,
            2: self.phase_2,
            1: self.phase_1,
            0: self.phase_0,
        }
        return mapping.get(phase, self.unknown)


# ─────────────────────────────────────────────────────────────────────────────
# Resistance gate
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResistanceConfig:
    """Resistance hard gate parameters.

    Drugs annotated at a resistance level are capped at `hard_cap` regardless
    of all other evidence. This prevents a drug like Erlotinib from ranking
    highly for EGFR T790M just because OpenTargets has a good association score.
    """
    levels: frozenset = field(
        default_factory=lambda: frozenset({"LEVEL_R1", "LEVEL_R2"})
    )
    hard_cap: float = 0.08  # below LEVEL_4 effective score (~0.20×0.25 weight)


# ─────────────────────────────────────────────────────────────────────────────
# Safety penalty
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SafetyConfig:
    """Safety penalty parameters.

    The raw `safety_score_penalty` from the tox/ADME pipeline is subtracted
    from the rank score.  For FDA-approved drugs the penalty is capped because
    their clinical record already accounts for most known safety liabilities.

    Rationale for the asymmetry:
      - Approved drugs have extensive post-marketing safety data; aggressive
        penalisation based on QSAR alerts alone would be misleading.
      - De-novo / unapproved compounds have no clinical record, so the full
        QSAR penalty should apply and will often produce very low rank scores.
    """
    approved_drug_max_penalty: float = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Source diversity penalty
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiversityPenaltyConfig:
    """Penalty for drugs supported by only one evidence source.

    A drug ranked purely on one source (e.g., only OpenTargets association)
    has a fundamentally wider uncertainty than one confirmed by three or more
    independent sources.  This penalty makes that uncertainty explicit in the
    rank score rather than only in the CI.
    """
    single_source_factor: float = 0.78   # rank *= this when only 1 source


# ─────────────────────────────────────────────────────────────────────────────
# Uncertainty / confidence interval
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UncertaintyConfig:
    """Parameters for CI width and confidence level classification.

    CI half-width = epistemic_hw (from missing sources) + aleatoric_hw
                    (from variance across available scores), capped at max_hw.
    """
    epistemic_hw_per_missing_source: float = 0.07   # ±0.07 per absent source
    max_half_width: float = 0.40
    single_source_aleatoric_hw: float = 0.12        # when only 1 source available

    # Thresholds for labelling confidence level
    high_confidence_threshold: float = 0.80    # evidence_completeness ≥ → HIGH
    medium_confidence_threshold: float = 0.50  # ≥ → MEDIUM; below → LOW


# ─────────────────────────────────────────────────────────────────────────────
# Low VAF uncertainty boost
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LowVAFConfig:
    """Confidence interval boost for low variant allele frequency variants.

    Low VAF variants may be subclonal, artefactual, or sequencing noise.
    When VAF is below threshold, widen the CI to reflect higher uncertainty
    in whether the mutation is the dominant driver.

    References:
      - Jamal-Hanjani et al., NEJM 2017 — subclonal mutations and treatment response
      - Hao et al., Nat Methods 2020 — VAF thresholds for reliable calling
    """
    low_vaf_threshold: float = 0.05        # VAF < 5% → low_vaf_ci_boost added
    very_low_vaf_threshold: float = 0.02   # VAF < 2% → very_low_vaf_ci_boost added
    low_vaf_ci_boost: float = 0.08         # added to CI half-width when VAF < 5%
    very_low_vaf_ci_boost: float = 0.15    # added to CI half-width when VAF < 2%
    # Also apply a small score discount for very low VAF: the mutation may be
    # subclonal and the drug may not work against the majority clone.
    very_low_vaf_score_discount: float = 0.05


# ─────────────────────────────────────────────────────────────────────────────
# Co-mutation context penalty
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CoMutationConfig:
    """Penalty applied when co-occurring pathway-competing mutations are detected.

    When multiple mutations activate the same or competing signalling pathways,
    a single-target drug may have reduced efficacy — the other pathway branch
    can compensate.  The penalty is per competing pathway gene found and caps at
    max_co_mutation_penalty.

    Pathway groups: drugs targeting one gene in a group receive the penalty
    when another gene in the same group also carries a somatic mutation.

    Note: Compound resistance (e.g. T790M + C797S → Osimertinib resistant) is
    handled separately via the resistance hard gate and oncokb_evidence table.
    This penalty is for suboptimal (not contra-indicated) scenarios.

    References:
      - Boros et al., Oncogene 2019 — co-mutation patterns and drug resistance
      - Jamal-Hanjani et al. NEJM 2017 — intratumour heterogeneity
    """
    competing_pathway_penalty: float = 0.05   # per competing pathway hit
    max_co_mutation_penalty: float = 0.12

    # Pathway groups — genes that can compensate for each other's inhibition.
    # Keys are informal group labels; values are frozensets of gene names.
    pathway_groups: tuple = field(default_factory=lambda: (
        frozenset({"KRAS", "NRAS", "HRAS", "BRAF", "RAF1", "MAP2K1", "MAPK1", "ERK2"}),
        frozenset({"PIK3CA", "PTEN", "AKT1", "AKT2", "MTOR", "TSC1", "TSC2", "RICTOR"}),
        frozenset({"EGFR", "ERBB2", "ERBB3", "MET", "ALK", "ROS1", "RET", "FGFR1",
                   "FGFR2", "FGFR3"}),
        frozenset({"CDK4", "CDK6", "CDKN2A", "RB1", "CCND1"}),
        frozenset({"TP53", "MDM2", "MDM4"}),
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Ranking robustness boosts/penalties
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RobustnessConfig:
        """Parameters that improve ranking discrimination on similar-evidence drugs.

        These terms intentionally avoid benchmark-specific heuristics. They encode
        generic behavior expected by clinicians:
            - candidates with internally conflicting evidence should be downgraded;
            - candidates supported by both molecular actionability and external
                clinical evidence should be nudged upward;
            - multi-source support should be preferred over single-source optimism.

        Calibration policy:
            - keep terms small so they break ties but do not dominate OncoKB L1/L2;
            - keep all constants explicit and auditable in config;
            - preserve resistance and high-evidence safety constraints in ranking.py.
        """
        # Penalize high disagreement across available source scores.
        variance_penalty_factor: float = 0.10
        max_variance_penalty: float = 0.12

        # Bonus for convergent translational evidence (OncoKB + CIViC).
        translational_bonus_factor: float = 0.08
        max_translational_bonus: float = 0.08

        # Bonus for richer evidence coverage (2+ contributing sources).
        multi_source_bonus_per_source: float = 0.01
        multi_source_bonus_cap: float = 0.04


# ─────────────────────────────────────────────────────────────────────────────
# Clinical-priority tie-breaker
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClinicalPriorityRule:
    """Auditable rule for a small SOC preference boost in near-tie scenarios.

    The ranking engine applies this only when candidates are already close in
    score (configured by ``ClinicalPriorityConfig.tie_score_window``). This is
    intended to resolve practical ordering issues between similarly ranked
    Level 1/2 options, not to override core evidence scoring.
    """
    drug_contains: str
    boost: float
    rationale: str
    gene_contains: Optional[str] = None
    cancer_contains: Optional[str] = None
    oncokb_levels: tuple[str, ...] = ("LEVEL_1", "LEVEL_2")


@dataclass
class ClinicalPriorityConfig:
    """Small, configurable boost for modern SOC drugs in near-tie ordering.

    Calibration guidance:
      - keep boosts in the +0.02 to +0.05 range;
      - use only for clinically accepted ordering preferences;
      - apply only within ``tie_score_window`` to avoid broad score distortion.
    """
    enabled: bool = True
    tie_score_window: float = 0.03
    max_total_boost: float = 0.05
    rules: tuple[ClinicalPriorityRule, ...] = field(default_factory=lambda: (
        ClinicalPriorityRule(
            drug_contains="osimertinib",
            gene_contains="EGFR",
            boost=0.05,
            rationale="Preferred modern EGFR SOC option in relevant resistance context.",
        ),
        ClinicalPriorityRule(
            drug_contains="trastuzumab deruxtecan",
            gene_contains="ERBB2",
            cancer_contains="gastric",
            boost=0.04,
            rationale="Preferred modern HER2-directed option in gastric context.",
        ),
        ClinicalPriorityRule(
            drug_contains="enhertu",
            gene_contains="ERBB2",
            cancer_contains="gastric",
            boost=0.04,
            rationale="Brand alias for trastuzumab deruxtecan; same ordering preference.",
        ),
        ClinicalPriorityRule(
            drug_contains="lorlatinib",
            gene_contains="ALK",
            boost=0.03,
            rationale="Later-generation ALK inhibitor often preferred in refractory setting.",
        ),
        ClinicalPriorityRule(
            drug_contains="gilteritinib",
            gene_contains="FLT3",
            boost=0.03,
            rationale="Preferred FLT3 option in relapsed/refractory AML context.",
        ),
    ))


# ─────────────────────────────────────────────────────────────────────────────
# High-evidence score floor
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HighEvidenceFloorConfig:
    """Minimum score floors for high-evidence OncoKB levels.

    Guarantees that LEVEL_1 and LEVEL_2 drugs score above unvalidated
    candidates even when other evidence sources are absent.  Applied
    after the source-diversity penalty and before the resistance hard gate.

    Rationale: an FDA-approved biomarker-matched drug (L1) should NEVER
    rank below a structurally attractive but clinically unvalidated compound
    just because DiffDock/AlphaMissense data are missing in offline mode.
    """
    l1_min_score: float = 0.70   # LEVEL_1 — FDA-approved, same tumour type
    l2_min_score: float = 0.55   # LEVEL_2 — standard-of-care / approved other tumour type


# ─────────────────────────────────────────────────────────────────────────────
# "No strong candidate" detection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NoDrugConfig:
    """Thresholds for detecting cases where no strong therapeutic option exists.

    When the best-ranked candidate's rank_score falls below no_drug_threshold,
    the report should prominently state that no strong therapeutic option was
    identified — rather than silently surfacing a weak candidate as if it were
    actionable.

    When top score is between warn_threshold and no_drug_threshold, a warning
    is shown: "weak evidence — not actionable without further validation".
    """
    no_drug_threshold: float = 0.20   # score ≤ this → "no strong candidate"
    warn_threshold: float = 0.35      # score ≤ this → "weak evidence" warning


# ─────────────────────────────────────────────────────────────────────────────
# Top-level config
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RankingConfig:
    """Complete, immutable configuration for the drug ranking engine.

    Usage — default (no customisation):
        from api.ai.ranking_config import DEFAULT_CONFIG

    Usage — ablation study (zero out DiffDock weight):
        from api.ai.ranking_config import RankingConfig, EvidenceWeights
        ablation_cfg = RankingConfig(
            weights=EvidenceWeights(binding=0.0, opentargets=0.25, oncokb=0.31,
                                    alphamissense=0.125, clinical_phase=0.125, civic=0.125)
        )

    Usage — custom sensitivity:
        cfg = RankingConfig()
        cfg.weights.oncokb = 0.35
        cfg.weights.opentargets = 0.15
        cfg.weights.validate()
    """
    weights:          EvidenceWeights       = field(default_factory=EvidenceWeights)
    resistance:       ResistanceConfig      = field(default_factory=ResistanceConfig)
    safety:           SafetyConfig          = field(default_factory=SafetyConfig)
    uncertainty:      UncertaintyConfig     = field(default_factory=UncertaintyConfig)
    diversity_penalty: DiversityPenaltyConfig = field(default_factory=DiversityPenaltyConfig)
    high_evidence_floor: HighEvidenceFloorConfig = field(default_factory=HighEvidenceFloorConfig)
    oncokb_scores:    OncoKBScores          = field(default_factory=OncoKBScores)
    civic_scores:     CIViCScores           = field(default_factory=CIViCScores)
    phase_scores:     PhaseScores           = field(default_factory=PhaseScores)
    low_vaf:          LowVAFConfig          = field(default_factory=LowVAFConfig)
    co_mutation:      CoMutationConfig      = field(default_factory=CoMutationConfig)
    robustness:       RobustnessConfig      = field(default_factory=RobustnessConfig)
    clinical_priority: ClinicalPriorityConfig = field(default_factory=ClinicalPriorityConfig)
    no_drug:          NoDrugConfig          = field(default_factory=NoDrugConfig)

    def validate(self) -> None:
        """Validate all sub-configs."""
        self.weights.validate()

    def describe(self) -> str:
        """Return a human-readable summary of the active configuration."""
        w = self.weights
        return (
            f"RankingConfig — weights: DiffDock={w.binding}, OT={w.opentargets}, "
            f"OncoKB={w.oncokb}, AM={w.alphamissense}, Phase={w.clinical_phase}, "
            f"CIViC={w.civic} | "
            f"resistance_cap={self.resistance.hard_cap} | "
            f"diversity_factor={self.diversity_penalty.single_source_factor} | "
            f"approved_max_penalty={self.safety.approved_drug_max_penalty} | "
            f"low_vaf_threshold={self.low_vaf.low_vaf_threshold} | "
            f"tie_window={self.clinical_priority.tie_score_window} | "
            f"no_drug_threshold={self.no_drug.no_drug_threshold}"
        )


# Module-level default used by ranking.py when no custom config is supplied.
DEFAULT_CONFIG: RankingConfig = RankingConfig()
