"""Drug-repurposing scoring module.

Provides a lightweight wrapper that applies the composite ranking algorithm
(defined in api/ai/ranking.py) to a list of raw drug candidates fetched from
OpenTargets / ChEMBL / OncoKB.  Callers outside the api/ tree (e.g.
Nextflow scripts, notebooks) can import from here without depending on the
full FastAPI stack.

Usage
-----
>>> from ai.repurposing import score_repurposing_candidates
>>> ranked = score_repurposing_candidates(candidates, target_gene="TP53")
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path bootstrapping
# ---------------------------------------------------------------------------
# When imported from the repo root, add api/ to sys.path so that
# api/ai/ranking.py is importable as `api.ai.ranking`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def score_repurposing_candidates(
    candidates: list[dict],
    target_gene: str | None = None,
    *,
    top_n: int = 10,
) -> list[dict]:
    """Score and rank a list of drug candidates using the composite algorithm.

    Parameters
    ----------
    candidates:
        Raw candidate dicts.  Each dict may include any of the keys consumed
        by ``api.ai.ranking.rank_candidates``:
        - ``drug_name`` (str)
        - ``chembl_id`` (str | None)
        - ``binding_score`` (float | None)   — DiffDock docking score
        - ``opentargets_score`` (float | None)
        - ``oncokb_level`` (str | None)       — e.g. "LEVEL_1"
        - ``alphamissense_score`` (float | None)
        - ``max_phase`` (int | None)          — 0–4
        - ``is_approved`` (bool | None)
    target_gene:
        Informational; logged but not used in scoring.
    top_n:
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Candidates in descending rank-score order, each augmented with a
        ``rank_score`` key (0.0–1.0).
    """
    if not candidates:
        return []

    try:
        from api.ai.ranking import rank_candidates  # type: ignore[import]
    except ModuleNotFoundError:
        # Fallback: try relative import inside api/ working directory
        try:
            from ai.ranking import rank_candidates  # type: ignore[import]
        except ModuleNotFoundError:
            logger.error(
                "[repurposing] Cannot import rank_candidates — api/ai/ranking.py "
                "not found on sys.path.  Returning candidates unranked."
            )
            return candidates[:top_n]

    if target_gene:
        logger.debug("[repurposing] scoring %d candidates for gene %s", len(candidates), target_gene)

    ranked = rank_candidates(candidates[:top_n])
    return ranked


__all__ = ["score_repurposing_candidates"]
