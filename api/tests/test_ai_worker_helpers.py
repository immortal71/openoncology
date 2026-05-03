"""Unit tests for ai_worker helper functions.

Tests the pure, side-effect-free helper functions in api/workers/ai_worker.py
without requiring Redis, Celery, a running database, or any external service.

Strategy: import *only* the helpers by patching the heavy Celery decorator at
module load time so that the @celery_app.task(...) call becomes a no-op that
returns the plain function.
"""

import sys
import os
import types
import importlib
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── Lazy-import helpers without bootstrapping Celery ────────────────────────

def _load_ai_worker_helpers():
    """Import ai_worker and return the module, injecting a mock celery_app."""
    # Provide a minimal fake 'workers' package so the Celery import doesn't fail
    fake_workers = types.ModuleType("workers")
    mock_celery = MagicMock()
    # Make @celery_app.task(...) act as a transparent decorator
    mock_celery.task.return_value = lambda fn: fn
    fake_workers.celery_app = mock_celery
    sys.modules.setdefault("workers", fake_workers)
    sys.modules["workers"].celery_app = mock_celery  # type: ignore[assignment]

    # Reload if already cached (clean slate per test run)
    if "workers.ai_worker" in sys.modules:
        mod = sys.modules["workers.ai_worker"]
    else:
        import workers.ai_worker as mod  # noqa: PLC0415
    return mod


_w = _load_ai_worker_helpers()
_hgvs_to_short = _w._hgvs_to_short
_gene_to_uniprot = _w._gene_to_uniprot
_extract_oncokb_treatment_names = _w._extract_oncokb_treatment_names


# ─────────────────────────────────────────────────────────────────────────────
# _hgvs_to_short  —  p.Arg175His → R175H
# ─────────────────────────────────────────────────────────────────────────────

class TestHgvsToShort:
    # Three-letter → one-letter conversions
    def test_arg_to_r(self):
        assert _hgvs_to_short("p.Arg175His") == "R175H"

    def test_leu_to_l(self):
        assert _hgvs_to_short("p.Leu858Arg") == "L858R"

    def test_val_to_v(self):
        assert _hgvs_to_short("p.Val600Glu") == "V600E"

    def test_gly_to_g(self):
        assert _hgvs_to_short("p.Gly12Asp") == "G12D"

    def test_thr_790_met(self):
        assert _hgvs_to_short("p.Thr790Met") == "T790M"

    def test_phe_to_f(self):
        # "Del" is not in AA3 map so it passes through as-is: "F508Del"
        result = _hgvs_to_short("p.Phe508Del")
        assert result == "F508Del"

    # Short-form passthrough
    def test_already_short_r175h(self):
        assert _hgvs_to_short("R175H") == "R175H"

    def test_already_short_v600e(self):
        assert _hgvs_to_short("V600E") == "V600E"

    def test_already_short_without_p_prefix(self):
        assert _hgvs_to_short("L858R") == "L858R"

    def test_star_termination_codon(self):
        # Ter → * is in the AA3 map
        assert _hgvs_to_short("p.Arg213Ter") == "R213*"

    # Invalid / unrecognisable inputs
    def test_none_returns_none(self):
        assert _hgvs_to_short("p.XYZ999ZZZ") is None

    def test_empty_string_returns_none(self):
        assert _hgvs_to_short("") is None

    def test_numeric_only_returns_none(self):
        assert _hgvs_to_short("12345") is None

    def test_strips_p_dot_prefix(self):
        # Ensure p. prefix is handled even without a following uppercase
        result = _hgvs_to_short("p.Gly12Asp")
        assert result == "G12D"


# ─────────────────────────────────────────────────────────────────────────────
# _gene_to_uniprot  —  curated gene→UniProt mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneToUniprot:
    def test_tp53_known(self):
        assert _gene_to_uniprot("TP53") == "P04637"

    def test_kras_known(self):
        assert _gene_to_uniprot("KRAS") == "P01116"

    def test_braf_known(self):
        assert _gene_to_uniprot("BRAF") == "P15056"

    def test_egfr_known(self):
        assert _gene_to_uniprot("EGFR") == "P00533"

    def test_brca1_known(self):
        assert _gene_to_uniprot("BRCA1") == "P38398"

    def test_case_insensitive_lookup(self):
        assert _gene_to_uniprot("tp53") == "P04637"
        assert _gene_to_uniprot("Tp53") == "P04637"

    def test_unknown_gene_returns_none(self):
        assert _gene_to_uniprot("FAKEGENE999") is None

    def test_empty_string_returns_none(self):
        assert _gene_to_uniprot("") is None

    def test_all_listed_genes_have_uniprot(self):
        """Every gene in the curated table returns a non-empty UniProt ID."""
        known_genes = [
            "TP53", "KRAS", "BRAF", "EGFR", "PIK3CA", "PTEN",
            "APC", "BRCA1", "BRCA2", "CDKN2A", "RB1", "MYC",
            "ERBB2", "VHL", "MLH1", "MTOR", "IDH1", "IDH2",
            "FLT3", "KIT", "ABL1", "BCR", "ALK", "RET",
            "MET", "NRAS", "HRAS", "JAK2", "NPM1", "DNMT3A",
        ]
        for gene in known_genes:
            uid = _gene_to_uniprot(gene)
            assert uid is not None and uid != "", f"{gene} should have a UniProt ID"


# ─────────────────────────────────────────────────────────────────────────────
# _extract_oncokb_treatment_names  —  deep dict/list walker for drug names
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractOncokbTreatmentNames:
    def test_empty_list_returns_empty(self):
        assert _extract_oncokb_treatment_names([]) == []

    def test_flat_drug_name_key(self):
        treatments = [{"drugName": "Osimertinib"}]
        result = _extract_oncokb_treatment_names(treatments)
        assert "Osimertinib" in result

    def test_drug_string_key(self):
        treatments = [{"drug": "Erlotinib"}]
        result = _extract_oncokb_treatment_names(treatments)
        assert "Erlotinib" in result

    def test_nested_drugs_list(self):
        treatments = [
            {"drugs": [{"drugName": "Imatinib"}, {"drugName": "Dasatinib"}]}
        ]
        result = _extract_oncokb_treatment_names(treatments)
        assert "Imatinib" in result
        assert "Dasatinib" in result

    def test_deduplicates_drug_names(self):
        treatments = [
            {"drugName": "Vemurafenib"},
            {"drugName": "Vemurafenib"},
        ]
        result = _extract_oncokb_treatment_names(treatments)
        assert result.count("Vemurafenib") == 1

    def test_none_input_returns_empty(self):
        # _walk handles None gracefully — hits neither dict nor list branch
        result = _extract_oncokb_treatment_names([None])  # type: ignore[list-item]
        assert result == []

    def test_whitespace_only_names_skipped(self):
        treatments = [{"drugName": "   "}]
        result = _extract_oncokb_treatment_names(treatments)
        assert result == []

    def test_deeply_nested_names_extracted(self):
        treatments = [
            {
                "combinationTherapy": [
                    {"drugs": [{"drugName": "Trametinib"}]}
                ]
            }
        ]
        result = _extract_oncokb_treatment_names(treatments)
        assert "Trametinib" in result

    def test_returns_sorted_list(self):
        treatments = [{"drugName": "Zebrafenib"}, {"drugName": "Afatinib"}]
        result = _extract_oncokb_treatment_names(treatments)
        assert result == sorted(result)
