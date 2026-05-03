#!/usr/bin/env python3
"""Holdout Validation Framework — OpenOncology

Implements train/holdout split validation to detect overfitting and validate
that P@3 performance is genuinely improving (not just gaming metrics).

Key principle: P@3 should NOT improve just because n increases. If it does,
the benchmark is contaminated or the model is overfitting.

Implements:
  - Split cases into train (70%) and holdout (30%)
  - Track holdout cases separately in benchmark
  - Compute metrics independently for train vs holdout
  - Validate P@3 stability: train_p3 ≈ holdout_p3 (within margin)
  - Report overfitting detector: if holdout_p3 < 0.80 * train_p3, flag overfitting

Usage:
    from scripts.holdout_validation import split_train_holdout, validate_p3_stability
    train_cases, holdout_cases = split_train_holdout(all_cases, holdout_frac=0.30)
    metrics = validate_p3_stability(train_metrics, holdout_metrics)
    print(metrics.overfitting_flag)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any
import random

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


@dataclass
class HoldoutValidationMetrics:
    """Metrics tracking train vs holdout performance."""
    
    train_p3: float
    holdout_p3: float
    train_hit_at_3: float
    holdout_hit_at_3: float
    train_false_positive_rate: float
    holdout_false_positive_rate: float
    
    # Stability metrics
    p3_degradation: float  # (train - holdout) / train * 100, should be < 5%
    hit_at_3_degradation: float
    fpr_increase: float  # (holdout - train) / train * 100, should be < 2pp
    
    # Overfitting flags
    is_overfitting: bool  # True if holdout_p3 < 0.80 * train_p3
    is_stable: bool  # True if all degradations within acceptable bounds
    
    def summary(self) -> str:
        """Human-readable summary of stability."""
        status = "✅ STABLE" if self.is_stable else "⚠️ DEGRADATION"
        
        return f"""
Holdout Validation Summary: {status}

Train Set:
  P@3: {self.train_p3:.3f}
  Hit@3: {self.train_hit_at_3:.3f}
  FP Rate: {self.train_false_positive_rate:.3f}

Holdout Set (30% unseen):
  P@3: {self.holdout_p3:.3f}
  Hit@3: {self.holdout_hit_at_3:.3f}
  FP Rate: {self.holdout_false_positive_rate:.3f}

Degradation (Train → Holdout):
  P@3 degradation: {self.p3_degradation:.1f}% (acceptable: < 5%)
  Hit@3 degradation: {self.hit_at_3_degradation:.1f}% (acceptable: < 5%)
  FP rate increase: {self.fpr_increase:.1f}pp (acceptable: < 2pp)

Overfitting Detection:
  Overfitting detected: {'YES - holdout P@3 collapsed' if self.is_overfitting else 'No'}
  Performance stability: {'PASS - metrics stable across sets' if self.is_stable else 'FAIL - metrics degraded'}
"""


def split_train_holdout(
    cases: list[dict[str, Any]],
    holdout_frac: float = 0.30,
    seed: int = 42,
    preserve_difficulty_distribution: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split cases into train (70%) and holdout (30%) sets.
    
    Args:
        cases: All benchmark cases
        holdout_frac: Fraction for holdout (default 0.30 = 30%)
        seed: Random seed for reproducibility
        preserve_difficulty_distribution: If True, ensure holdout has same
            difficulty distribution as train set
    
    Returns:
        (train_cases, holdout_cases) tuple with holdout_cases marked
    """
    random.seed(seed)
    
    if preserve_difficulty_distribution:
        # Group by difficulty
        by_difficulty: dict[str, list] = {}
        for case in cases:
            difficulty = case.get("difficulty", "UNKNOWN")
            if difficulty not in by_difficulty:
                by_difficulty[difficulty] = []
            by_difficulty[difficulty].append(case)
        
        train_cases = []
        holdout_cases = []
        
        # Split each difficulty group proportionally
        for difficulty, group in by_difficulty.items():
            random.shuffle(group)
            split_idx = int(len(group) * (1 - holdout_frac))
            train_cases.extend(group[:split_idx])
            holdout_cases.extend(group[split_idx:])
    else:
        # Simple random split
        shuffled = cases.copy()
        random.shuffle(shuffled)
        split_idx = int(len(shuffled) * (1 - holdout_frac))
        train_cases = shuffled[:split_idx]
        holdout_cases = shuffled[split_idx:]
    
    # Mark holdout cases for tracking
    for case in holdout_cases:
        case["is_holdout"] = True
    
    logger.info(
        f"Split {len(cases)} cases into train ({len(train_cases)}) and "
        f"holdout ({len(holdout_cases)}). Holdout difficulty distribution:"
    )
    
    # Log distribution
    holdout_by_difficulty = {}
    for case in holdout_cases:
        diff = case.get("difficulty", "UNKNOWN")
        holdout_by_difficulty[diff] = holdout_by_difficulty.get(diff, 0) + 1
    
    for diff, count in sorted(holdout_by_difficulty.items()):
        logger.info(f"  {diff}: {count} cases")
    
    return train_cases, holdout_cases


def compute_p3_stability(
    train_metrics: dict[str, float],
    holdout_metrics: dict[str, float],
    acceptable_p3_degradation: float = 0.05,  # 5%
    acceptable_fpr_increase: float = 0.02,  # 2 percentage points
) -> HoldoutValidationMetrics:
    """Compute stability metrics comparing train vs holdout.
    
    Args:
        train_metrics: Dict with keys: p3, hit_at_3, false_positive_rate
        holdout_metrics: Dict with same keys
        acceptable_p3_degradation: Max acceptable relative degradation
        acceptable_fpr_increase: Max acceptable absolute increase
    
    Returns:
        HoldoutValidationMetrics with stability assessment
    """
    train_p3 = train_metrics.get("p3", 0.0)
    holdout_p3 = holdout_metrics.get("p3", 0.0)
    
    train_hit_at_3 = train_metrics.get("hit_at_3", 0.0)
    holdout_hit_at_3 = holdout_metrics.get("hit_at_3", 0.0)
    
    train_fpr = train_metrics.get("false_positive_rate", 0.0)
    holdout_fpr = holdout_metrics.get("false_positive_rate", 0.0)
    
    # Compute degradation
    p3_degradation = (train_p3 - holdout_p3) / train_p3 * 100 if train_p3 > 0 else 0.0
    hit_at_3_degradation = (train_hit_at_3 - holdout_hit_at_3) / train_hit_at_3 * 100 if train_hit_at_3 > 0 else 0.0
    fpr_increase = (holdout_fpr - train_fpr) * 100  # In percentage points
    
    # Check for overfitting (holdout P@3 collapsed)
    is_overfitting = holdout_p3 < 0.80 * train_p3 if train_p3 > 0 else False
    
    # Check for stability
    is_stable = (
        p3_degradation < acceptable_p3_degradation * 100
        and hit_at_3_degradation < acceptable_p3_degradation * 100
        and fpr_increase < acceptable_fpr_increase * 100
        and not is_overfitting
    )
    
    return HoldoutValidationMetrics(
        train_p3=train_p3,
        holdout_p3=holdout_p3,
        train_hit_at_3=train_hit_at_3,
        holdout_hit_at_3=holdout_hit_at_3,
        train_false_positive_rate=train_fpr,
        holdout_false_positive_rate=holdout_fpr,
        p3_degradation=p3_degradation,
        hit_at_3_degradation=hit_at_3_degradation,
        fpr_increase=fpr_increase,
        is_overfitting=is_overfitting,
        is_stable=is_stable,
    )


def split_and_save(
    cases: list[dict[str, Any]],
    output_train: str = "api/services/benchmark_train.json",
    output_holdout: str = "api/services/benchmark_holdout.json",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split cases and save to JSON files for reproducibility.
    
    Args:
        cases: All cases to split
        output_train: Path to save train cases
        output_holdout: Path to save holdout cases
    
    Returns:
        (train_cases, holdout_cases) tuple
    """
    train_cases, holdout_cases = split_train_holdout(cases, preserve_difficulty_distribution=True)
    
    # Save for reproducibility
    with open(output_train, "w") as f:
        json.dump(train_cases, f, indent=2)
    
    with open(output_holdout, "w") as f:
        json.dump(holdout_cases, f, indent=2)
    
    logger.info(f"Saved {len(train_cases)} train cases to {output_train}")
    logger.info(f"Saved {len(holdout_cases)} holdout cases to {output_holdout}")
    
    return train_cases, holdout_cases


if __name__ == "__main__":
    # Quick test
    from api.services.benchmark import TRIAL_DERIVED_CASES
    
    print(f"Testing split on {len(TRIAL_DERIVED_CASES)} trial cases...")
    train, holdout = split_train_holdout(
        TRIAL_DERIVED_CASES,
        holdout_frac=0.30,
        preserve_difficulty_distribution=True,
    )
    
    print(f"\nTrain: {len(train)} cases")
    print(f"Holdout: {len(holdout)} cases (marked with is_holdout=True)")
    
    print("\nSample metrics comparison:")
    train_metrics = {"p3": 0.545, "hit_at_3": 0.937, "false_positive_rate": 0.037}
    holdout_metrics = {"p3": 0.530, "hit_at_3": 0.920, "false_positive_rate": 0.040}
    
    stability = compute_p3_stability(train_metrics, holdout_metrics)
    print(stability.summary())
