"""
Unit tests for api/ai/ranking.py
"""
import pytest
from ai.ranking import compute_rank_score, rank_candidates, DrugScoreComponents


# ── compute_rank_score tests ──────────────────────────────────────────────────

def test_all_components_score_in_range():
    """All score components provided → result is in range [0.0, 1.0]"""
    components = DrugScoreComponents(
        binding_score=0.8,
        opentargets_score=0.7,
        oncokb_level="LEVEL_1",
        alphamissense_score=0.6,
        max_phase=3,
    )
    score = compute_rank_score(components)
    assert 0.0 <= score <= 1.0


def test_binding_score_none_redistributes_weight():
    """binding_score=None → weight redistributed, score is still valid"""
    components = DrugScoreComponents(
        binding_score=None,
        opentargets_score=0.7,
        oncokb_level="LEVEL_1",
        alphamissense_score=0.6,
        max_phase=3,
    )
    score = compute_rank_score(components)
    assert 0.0 <= score <= 1.0


def test_all_none_returns_zero():
    """All inputs are None → returns 0.0"""
    components = DrugScoreComponents()
    assert compute_rank_score(components) == 0.0


def test_level1_oncokb_approved_scores_high():
    """Level 1 OncoKB + approved drug → scores near top of ranking"""
    components = DrugScoreComponents(
        oncokb_level="LEVEL_1",
        is_approved=True,
    )
    score = compute_rank_score(components)
    assert score >= 0.8


# ── rank_candidates tests ─────────────────────────────────────────────────────

def test_rank_candidates_sorted_descending():
    """rank_candidates() returns list sorted descending by rank_score"""
    candidates = [
        {"binding_score": 0.2, "opentargets_score": 0.1},
        {"binding_score": 0.9, "opentargets_score": 0.9, "is_approved": True},
        {"binding_score": 0.5, "opentargets_score": 0.5},
    ]
    ranked = rank_candidates(candidates)
    scores = [c["rank_score"] for c in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_candidates_attaches_rank_score():
    """rank_candidates() attaches rank_score to each candidate"""
    candidates = [{"binding_score": 0.5}]
    ranked = rank_candidates(candidates)
    assert "rank_score" in ranked[0]