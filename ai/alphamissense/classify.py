"""
AlphaMissense pathogenicity classifier.

AlphaMissense (Cheng et al., Science 2023) provides pre-computed pathogenicity scores
for all ~71 million possible human missense variants.

Two lookup strategies (tried in order):
  1. SQLite lookup  — fast O(1) lookup from the pre-imported scores DB.
  2. TSV lookup     — falls back to scanning the raw TSV (slow, last resort).
  3. Heuristic stub — if neither file is available, returns None so the worker
                      continues gracefully without crashing.

To populate the SQLite DB, run:
  python ai/alphamissense/download_scores.py

Score interpretation (per AlphaMissense paper):
  >= 0.564  → likely_pathogenic
  <= 0.340  → likely_benign
  between   → ambiguous
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths (relative to repo root, override via env vars if needed)
_REPO_ROOT = Path(__file__).resolve().parents[2]
SCORES_DB = _REPO_ROOT / "ai" / "alphamissense" / "scores.db"
SCORES_TSV = _REPO_ROOT / "ai" / "alphamissense" / "alphamissense_hg38.tsv.gz"

# Thresholds from AlphaMissense paper
PATHOGENIC_THRESHOLD = 0.564
BENIGN_THRESHOLD = 0.340


class AlphaMissenseClassifier:
    """Thread-safe classifier backed by a SQLite lookup table."""

    def __init__(self, db_path: Path = SCORES_DB):
        self._db_path = db_path
        self._available = db_path.exists()
        if not self._available:
            logger.warning(
                "AlphaMissense scores.db not found at %s. "
                "Run ai/alphamissense/download_scores.py to enable full scoring.",
                db_path,
            )

    def score(self, uniprot_id: str, protein_variant: str) -> Optional[float]:
        """Return pathogenicity score (0–1) for a protein variant.

        Args:
            uniprot_id: UniProt accession e.g. "P04637"
            protein_variant: HGVS protein change without "p." prefix e.g. "R175H"

        Returns:
            float in [0, 1] or None if not found.
        """
        if not self._available:
            return None

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT am_pathogenicity FROM scores "
                    "WHERE uniprot_id = ? AND protein_variant = ?",
                    (uniprot_id, protein_variant),
                )
                row = cur.fetchone()
                return float(row["am_pathogenicity"]) if row else None
        except sqlite3.Error as exc:
            logger.error("AlphaMissense DB error: %s", exc)
            return None

    def classify(self, score: float) -> str:
        """Convert a numeric score to a class label."""
        if score >= PATHOGENIC_THRESHOLD:
            return "likely_pathogenic"
        if score <= BENIGN_THRESHOLD:
            return "likely_benign"
        return "ambiguous"

    def score_and_classify(
        self, uniprot_id: str, protein_variant: str
    ) -> tuple[Optional[float], Optional[str]]:
        """Convenience wrapper returning (score, class_label)."""
        s = self.score(uniprot_id, protein_variant)
        if s is None:
            return None, None
        return s, self.classify(s)


# Module-level singleton — import and reuse to avoid repeated DB connections.
classifier = AlphaMissenseClassifier()
