"""
Drug ranking algorithm for OpenOncology.

Combines scores from multiple evidence sources into a single rank_score [0, 1]:

  Source                  Weight   Notes
  ──────────────────────  ──────   ──────────────────────────────────────────
  DiffDock binding conf.   0.30    Normalised to [0,1] by score.py
  OpenTargets assoc.       0.25    Already [0,1] from API
  OncoKB actionability     0.25    Mapped: L1=1.0, L2=0.8, L3A=0.6, L3B=0.4,
                                           L4=0.2, R1=0.1, else=0.0
  AlphaMissense pathog.    0.10    [0,1] from classifier
  Clinical phase           0.10    Mapped: approved=1.0, ph4=0.9, ph3=0.7,
                                           ph2=0.5, ph1=0.3, preclinical=0.1

If a score component is unavailable (None), its weight is redistributed
proportionally among the remaining components so the total always sums to 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── OncoKB level mapping ──────────────────────────────────────────────────────

_ONCOKB_WEIGHTS: dict[str, float] = {
    "LEVEL_1": 1.00,
    "LEVEL_2": 0.80,
    "LEVEL_3A": 0.60,
    "LEVEL_3B": 0.40,
    "LEVEL_4": 0.20,
    "LEVEL_R1": 0.10,
    "LEVEL_R2": 0.05,
}


def _oncokb_score(level: Optional[str]) -> Optional[float]:
    if not level:
        return None
    return _ONCOKB_WEIGHTS.get(level.upper())


# ── Clinical phase mapping ────────────────────────────────────────────────────

def _phase_score(max_phase: Optional[int], is_approved: bool = False) -> Optional[float]:
    if is_approved or max_phase == 4:
        return 1.0
    mapping = {3: 0.70, 2: 0.50, 1: 0.30, 0: 0.10}
    if max_phase is None:
        return None
    return mapping.get(max_phase, 0.10)


# ── Main ranking function ─────────────────────────────────────────────────────

@dataclass
class DrugScoreComponents:
    binding_score: Optional[float] = None        # DiffDock [0,1]
    opentargets_score: Optional[float] = None    # OpenTargets [0,1]
    oncokb_level: Optional[str] = None           # e.g. "LEVEL_1"
    alphamissense_score: Optional[float] = None  # [0,1]
    max_phase: Optional[int] = None              # clinical trial phase
    is_approved: bool = False


def compute_rank_score(components: DrugScoreComponents) -> float:
    """Return a rank_score in [0, 1] combining all available evidence.

    Missing components are handled by redistributing their weight.
    """
    # Base scores and weights
    raw: list[tuple[Optional[float], float]] = [
        (components.binding_score,                              0.30),
        (components.opentargets_score,                         0.25),
        (_oncokb_score(components.oncokb_level),               0.25),
        (components.alphamissense_score,                       0.10),
        (_phase_score(components.max_phase, components.is_approved), 0.10),
    ]

    available = [(score, weight) for score, weight in raw if score is not None]
    if not available:
        return 0.0

    total_weight = sum(w for _, w in available)
    if total_weight == 0:
        return 0.0

    # Normalise weights so they sum to 1.0 even with missing components
    rank = sum(score * (weight / total_weight) for score, weight in available)
    return round(min(max(rank, 0.0), 1.0), 4)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Given a list of drug dicts (from OpenTargets + ChEMBL + DiffDock),
    compute and attach a rank_score to each, then sort descending.

    Expected keys per candidate (all optional):
      binding_score, opentargets_score, oncokb_level, alphamissense_score,
      max_phase, is_approved, chembl_id, drug_name, mechanism, action_type
    """
    for c in candidates:
        components = DrugScoreComponents(
            binding_score=c.get("binding_score"),
            opentargets_score=c.get("opentargets_score"),
            oncokb_level=c.get("oncokb_level"),
            alphamissense_score=c.get("alphamissense_score"),
            max_phase=c.get("max_phase") or c.get("phase"),
            is_approved=bool(c.get("is_approved")),
        )
        c["rank_score"] = compute_rank_score(components)

    return sorted(candidates, key=lambda x: x["rank_score"], reverse=True)
