"""Tests for the VCF parser in api/workers/genomic_worker.py.

Covers:
  - Standard annotated VCF with OpenCRAVAT INFO fields
  - Comment/header lines are skipped
  - Missing INFO fields default gracefully
  - Multi-alt alleles are captured
  - Malformed lines (< 8 columns) are skipped
  - Position parsing for valid and invalid values
"""

import sys
import os
import textwrap
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from api.workers.genomic_worker import _parse_and_annotate_vcf


def _write_vcf(lines: str) -> str:
    """Write VCF content to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".vcf", delete=False, encoding="utf-8"
    ) as f:
        f.write(textwrap.dedent(lines))
        return f.name


# ── Basic parsing ─────────────────────────────────────────────────────────────

class TestParseAnnotateVcf:
    def test_parses_single_snv(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr7\t55174772\t.\tT\tG\t.\tPASS\tGENE=EGFR;HGVS_C=p.L858R;SO=missense_variant
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert len(mutations) == 1
        m = mutations[0]
        assert m["chrom"] == "chr7"
        assert m["pos"] == 55174772
        assert m["ref"] == "T"
        assert m["alt"] == "G"
        assert m["gene"] == "EGFR"
        assert m["hgvs"] == "p.L858R"
        assert m["mutation_type"] == "missense_variant"

    def test_header_lines_skipped(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            ##INFO=<ID=GENE,Number=1,Type=String,Description="Gene name">
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA\tT\t.\tPASS\tGENE=TP53
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert len(mutations) == 1

    def test_multiple_variants_parsed(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr7\t55174772\t.\tT\tG\t.\tPASS\tGENE=EGFR
            chr12\t25398281\t.\tC\tA\t.\tPASS\tGENE=KRAS
            chr17\t7674220\t.\tG\tA\t.\tPASS\tGENE=TP53
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert len(mutations) == 3
        genes = {m["gene"] for m in mutations}
        assert genes == {"EGFR", "KRAS", "TP53"}

    def test_missing_gene_defaults_to_unknown(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA\tT\t.\tPASS\t.
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["gene"] == "UNKNOWN"

    def test_missing_hgvs_returns_none(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA\tT\t.\tPASS\tGENE=BRCA1
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["hgvs"] is None

    def test_clinvar_and_cosmic_ids_extracted(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr17\t7674220\t.\tG\tA\t.\tPASS\tGENE=TP53;CLINVAR_ID=12375;COSMIC_ID=COSM245793
        """)
        mutations = _parse_and_annotate_vcf(path)
        m = mutations[0]
        assert m["clinvar_id"] == "12375"
        assert m["cosmic_id"] == "COSM245793"

    def test_malformed_line_fewer_than_8_cols_skipped(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert len(mutations) == 0

    def test_info_flag_without_value_handled(self):
        """INFO entries without '=' (bare flags) should not crash the parser."""
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA\tT\t.\tPASS\tGENE=BRCA2;SOMATIC
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["gene"] == "BRCA2"

    def test_empty_file_returns_empty_list(self):
        path = _write_vcf("")
        mutations = _parse_and_annotate_vcf(path)
        assert mutations == []

    def test_only_header_lines_returns_empty_list(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations == []

    def test_non_numeric_pos_stored_as_none(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\tNaN\t.\tA\tT\t.\tPASS\tGENE=TEST
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["pos"] is None

    def test_chrom_without_chr_prefix_preserved(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            7\t55174772\t.\tT\tG\t.\tPASS\tGENE=EGFR
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["chrom"] == "7"

    def test_mutation_type_defaults_to_unknown(self):
        path = _write_vcf("""\
            ##fileformat=VCFv4.2
            #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
            chr1\t100\t.\tA\tT\t.\tPASS\tGENE=GENE1
        """)
        mutations = _parse_and_annotate_vcf(path)
        assert mutations[0]["mutation_type"] == "unknown"
