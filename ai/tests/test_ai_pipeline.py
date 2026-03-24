"""Tests for the ai/ pipeline modules.

Covers:
  - ai/services/alphafold.py  (apply_mutation, get_uniprot_sequence)
  - ai/alphamissense/classify.py  (AlphaMissenseClassifier.classify)
  - ai/diffdock/score.py  (score_binding, _parse_confidence)

No real network calls — all external I/O is mocked.
"""

import math
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from ai.services.alphafold import apply_mutation, get_uniprot_sequence
from ai.alphamissense.classify import AlphaMissenseClassifier, PATHOGENIC_THRESHOLD, BENIGN_THRESHOLD


# ── apply_mutation tests ─────────────────────────────────────────────────────

class TestApplyMutation:
    """Tests for alphafold.apply_mutation()."""

    SAMPLE_SEQ = "MTEYKLVVVGAVGVGKSALT"  # 20 residues

    def test_substitution_single_letter(self):
        # V600E style — position 6 (1-indexed), V -> E
        result = apply_mutation(self.SAMPLE_SEQ, "p.V6E")
        assert result[5] == "E"
        assert len(result) == len(self.SAMPLE_SEQ)

    def test_substitution_three_letter(self):
        # Val600Glu style
        result = apply_mutation(self.SAMPLE_SEQ, "p.Val6Glu")
        assert result[5] == "E"

    def test_substitution_without_p_prefix(self):
        result = apply_mutation(self.SAMPLE_SEQ, "V6E")
        assert result[5] == "E"

    def test_substitution_preserves_other_residues(self):
        result = apply_mutation(self.SAMPLE_SEQ, "p.V6E")
        assert result[:5] == self.SAMPLE_SEQ[:5]
        assert result[6:] == self.SAMPLE_SEQ[6:]

    def test_deletion_range(self):
        # delete positions 3 through 5 (E746_A750del style)
        result = apply_mutation(self.SAMPLE_SEQ, "p.E3_K5del")
        assert len(result) == len(self.SAMPLE_SEQ) - 3
        # residues at index 0,1 preserved, index 5+ shifted
        assert result[:2] == self.SAMPLE_SEQ[:2]
        assert result[2:] == self.SAMPLE_SEQ[5:]

    def test_out_of_range_substitution_returns_unchanged(self):
        result = apply_mutation(self.SAMPLE_SEQ, "p.V999E")
        assert result == self.SAMPLE_SEQ

    def test_out_of_range_deletion_returns_unchanged(self):
        result = apply_mutation(self.SAMPLE_SEQ, "p.A900_A999del")
        assert result == self.SAMPLE_SEQ

    def test_unrecognised_notation_returns_unchanged(self):
        result = apply_mutation(self.SAMPLE_SEQ, "some_garbage")
        assert result == self.SAMPLE_SEQ

    def test_empty_hgvs_returns_unchanged(self):
        result = apply_mutation(self.SAMPLE_SEQ, "")
        assert result == self.SAMPLE_SEQ

    def test_position_one(self):
        # edge case: first residue
        result = apply_mutation(self.SAMPLE_SEQ, "p.M1A")
        assert result[0] == "A"
        assert result[1:] == self.SAMPLE_SEQ[1:]

    def test_last_position(self):
        # edge case: last residue
        last_pos = len(self.SAMPLE_SEQ)
        result = apply_mutation(self.SAMPLE_SEQ, f"p.T{last_pos}A")
        assert result[-1] == "A"
        assert result[:-1] == self.SAMPLE_SEQ[:-1]


# ── get_uniprot_sequence tests ───────────────────────────────────────────────

class TestGetUniprotSequence:
    """Tests for alphafold.get_uniprot_sequence() with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_returns_sequence_on_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"sequence": {"value": "MTEYKLVVV"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ai.services.alphafold.httpx.AsyncClient", return_value=mock_client):
            seq = await get_uniprot_sequence("EGFR")
            assert seq == "MTEYKLVVV"

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_results(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ai.services.alphafold.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="No UniProt entry"):
                await get_uniprot_sequence("FAKEGENE")

    @pytest.mark.asyncio
    async def test_raises_value_error_when_results_is_none(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ai.services.alphafold.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="No UniProt entry"):
                await get_uniprot_sequence("FAKEGENE")


# ── AlphaMissense classify tests ─────────────────────────────────────────────

class TestAlphaMissenseClassify:
    """Tests for AlphaMissenseClassifier.classify() boundary values."""

    def setup_method(self):
        # create classifier that doesn't need an actual DB
        self.clf = AlphaMissenseClassifier(db_path=Path("/nonexistent/scores.db"))

    def test_score_above_pathogenic_threshold(self):
        assert self.clf.classify(0.9) == "likely_pathogenic"

    def test_score_at_pathogenic_threshold(self):
        assert self.clf.classify(PATHOGENIC_THRESHOLD) == "likely_pathogenic"

    def test_score_below_benign_threshold(self):
        assert self.clf.classify(0.1) == "likely_benign"

    def test_score_at_benign_threshold(self):
        assert self.clf.classify(BENIGN_THRESHOLD) == "likely_benign"

    def test_score_in_ambiguous_range(self):
        mid = (BENIGN_THRESHOLD + PATHOGENIC_THRESHOLD) / 2
        assert self.clf.classify(mid) == "ambiguous"

    def test_score_just_above_benign_threshold(self):
        assert self.clf.classify(BENIGN_THRESHOLD + 0.001) == "ambiguous"

    def test_score_just_below_pathogenic_threshold(self):
        assert self.clf.classify(PATHOGENIC_THRESHOLD - 0.001) == "ambiguous"

    def test_score_zero(self):
        assert self.clf.classify(0.0) == "likely_benign"

    def test_score_one(self):
        assert self.clf.classify(1.0) == "likely_pathogenic"


# ── DiffDock score_binding tests ─────────────────────────────────────────────

class TestScoreBinding:
    """Tests for diffdock.score.score_binding() with mocked subprocess."""

    def test_returns_none_when_diffdock_not_installed(self):
        with patch("ai.diffdock.score.DIFFDOCK_DIR", Path("/nonexistent/DiffDock")):
            from ai.diffdock.score import score_binding
            result = score_binding("P04637", "CCO", "CHEMBL545")
            assert result is None

    def test_parse_confidence_extracts_score(self, tmp_path):
        # create a fake rank1 output file
        sdf_file = tmp_path / "rank1_confidence-1.50.sdf"
        sdf_file.write_text("fake sdf content")

        from ai.diffdock.score import _parse_confidence
        result = _parse_confidence(tmp_path)

        expected = round(1.0 / (1.0 + math.exp(1.50 / 2.0)), 4)
        assert result == expected

    def test_parse_confidence_returns_none_for_empty_dir(self, tmp_path):
        from ai.diffdock.score import _parse_confidence
        result = _parse_confidence(tmp_path)
        assert result is None

    def test_parse_confidence_positive_score(self, tmp_path):
        sdf_file = tmp_path / "rank1_confidence2.00.sdf"
        sdf_file.write_text("fake sdf content")

        from ai.diffdock.score import _parse_confidence
        result = _parse_confidence(tmp_path)

        expected = round(1.0 / (1.0 + math.exp(-2.00 / 2.0)), 4)
        assert result == expected

    def test_parse_confidence_zero_score(self, tmp_path):
        sdf_file = tmp_path / "rank1_confidence0.00.sdf"
        sdf_file.write_text("fake sdf content")

        from ai.diffdock.score import _parse_confidence
        result = _parse_confidence(tmp_path)

        assert result == 0.5  # sigmoid(0) = 0.5
