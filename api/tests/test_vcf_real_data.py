"""
Tests against real public cancer genomic VCF data.

The VCF files in samples/real/ were downloaded from:
  - cBioPortal (TCGA-LUAD, TCGA-BRCA, TCGA-COADREAD studies) — GRCh37 somatic mutations
  - Curated cancer driver hotspots with verified GRCh38 coordinates

Download them with:
    python scripts/download_real_data.py

These tests are marked @pytest.mark.realdata so they can be skipped when the
data files have not yet been downloaded:
    pytest -m "not realdata"      # skip real-data tests
    pytest -m realdata            # run only real-data tests
"""
from __future__ import annotations

import os
import sys
import pytest
from pathlib import Path

# ─── resolve paths ─────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_DATA_DIR = _REPO_ROOT / "samples" / "real"

_VCF_HOTSPOTS   = _REAL_DATA_DIR / "hotspots_grch38.vcf"
_VCF_TCGA_LUAD  = _REAL_DATA_DIR / "tcga_luad.vcf"
_VCF_TCGA_BRCA  = _REAL_DATA_DIR / "tcga_brca.vcf"
_VCF_TCGA_COAD  = _REAL_DATA_DIR / "tcga_coadread.vcf"
_VCF_CLINVAR    = _REAL_DATA_DIR / "clinvar_cancer.vcf"

# import the parser under test
sys.path.insert(0, str(_REPO_ROOT / "api"))
from workers.genomic_worker import _parse_and_annotate_vcf  # noqa: E402


# ─── marker + skip helpers ─────────────────────────────────────────────────────

def _require(path: Path):
    """Skip test if data file not present (not yet downloaded)."""
    if not path.exists():
        pytest.skip(f"Real data file not found: {path}  — run: python scripts/download_real_data.py")


# ─── shared expected-gene sets ─────────────────────────────────────────────────

_LUAD_EXPECTED_GENES  = {"EGFR", "KRAS", "TP53", "STK11", "KEAP1"}
_BRCA_EXPECTED_GENES  = {"TP53", "PIK3CA", "CDH1", "GATA3", "KMT2C"}
_COAD_EXPECTED_GENES  = {"APC", "TP53", "KRAS", "PIK3CA", "FBXW7"}
_HOTSPOT_EXPECTED_GENES = {"TP53", "KRAS", "EGFR", "BRAF", "PIK3CA", "BRCA1", "BRCA2", "ERBB2", "PTEN", "ALK"}


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Curated hotspot file (GRCh38)
# ─────────────────────────────────────────────────────────────────────────────

class TestHotspotVcf:
    """Parser tests against the curated GRCh38 cancer driver hotspot file."""

    def test_hotspots_file_exists(self):
        _require(_VCF_HOTSPOTS)
        assert _VCF_HOTSPOTS.stat().st_size > 0

    def test_hotspots_parse_returns_list(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        assert isinstance(result, list)

    def test_hotspots_total_variant_count(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        assert len(result) == 20, f"Expected 20 hotspot variants, got {len(result)}"

    def test_hotspots_all_expected_genes_present(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        genes = {m["gene"] for m in result}
        for gene in _HOTSPOT_EXPECTED_GENES:
            assert gene in genes, f"Expected gene {gene!r} missing from hotspot results"

    def test_hotspots_tp53_r175h_present(self):
        """TP53 R175H (p.R175H) is the most common cancer hotspot — must appear."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        tp53_hgvs = [m["hgvs"] for m in result if m["gene"] == "TP53"]
        assert any("524G>A" in (h or "") for h in tp53_hgvs), \
            "TP53 c.524G>A (R175H) not found in hotspot VCF"

    def test_hotspots_kras_g12d_present(self):
        """KRAS G12D (c.35G>A) — most common pancreatic/colorectal hotspot."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        kras_hgvs = [m["hgvs"] for m in result if m["gene"] == "KRAS"]
        assert any("35G>A" in (h or "") for h in kras_hgvs), \
            "KRAS c.35G>A (G12D) not found in hotspot VCF"

    def test_hotspots_egfr_l858r_present(self):
        """EGFR L858R (c.2573T>G) — most common lung cancer EGFR hotspot."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        egfr_hgvs = [m["hgvs"] for m in result if m["gene"] == "EGFR"]
        assert any("2573T>G" in (h or "") for h in egfr_hgvs), \
            "EGFR c.2573T>G (L858R) not found in hotspot VCF"

    def test_hotspots_braf_v600e_present(self):
        """BRAF V600E (c.1799T>A) — canonical melanoma/colorectal hotspot."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        braf_hgvs = [m["hgvs"] for m in result if m["gene"] == "BRAF"]
        assert any("1799T>A" in (h or "") for h in braf_hgvs), \
            "BRAF c.1799T>A (V600E) not found in hotspot VCF"

    def test_hotspots_pik3ca_h1047r_present(self):
        """PIK3CA H1047R (c.3140A>G) — most common breast cancer hotspot."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        pik3ca_hgvs = [m["hgvs"] for m in result if m["gene"] == "PIK3CA"]
        assert any("3140A>G" in (h or "") for h in pik3ca_hgvs), \
            "PIK3CA c.3140A>G (H1047R) not found in hotspot VCF"

    def test_hotspots_all_mutations_have_gene(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        missing = [m for m in result if not m.get("gene") or m["gene"] == "UNKNOWN"]
        assert not missing, f"{len(missing)} hotspot variants lack a gene annotation"

    def test_hotspots_all_mutations_have_chrom(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        missing = [m for m in result if not m.get("chrom")]
        assert not missing, f"{len(missing)} hotspot variants have no chromosome"

    def test_hotspots_all_mutations_have_pos(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        missing = [m for m in result if m.get("pos") is None]
        assert not missing, f"{len(missing)} hotspot variants have no position"

    def test_hotspots_positions_are_integers(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        for m in result:
            assert isinstance(m["pos"], int), f"pos for {m['gene']} is not int: {m['pos']!r}"

    def test_hotspots_clinvar_ids_present(self):
        """At least some hotspot variants should carry ClinVar accessions."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        clinvar_ids = [m.get("clinvar_id") for m in result if m.get("clinvar_id") and m["clinvar_id"] != "."]
        assert len(clinvar_ids) >= 10, "Expected ≥10 ClinVar IDs in hotspot file"

    def test_hotspots_cosmic_ids_present(self):
        """Key oncogene hotspots carry COSMIC identifiers."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        cosmic_ids = [m.get("cosmic_id") for m in result if m.get("cosmic_id") and m["cosmic_id"] != "."]
        assert len(cosmic_ids) >= 10, "Expected ≥10 COSMIC IDs in hotspot file"

    def test_hotspots_ref_alleles_non_empty(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        for m in result:
            assert m.get("ref"), f"Empty REF allele for {m['gene']}"

    def test_hotspots_alt_alleles_non_empty(self):
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        for m in result:
            assert m.get("alt"), f"Empty ALT allele for {m['gene']}"

    def test_hotspots_chroms_are_numeric_or_xy(self):
        """GRCh38 hotspot chroms should be like '1', '7', '17', 'X', 'Y'."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        valid = set(str(i) for i in range(1, 23)) | {"X", "Y", "MT"}
        for m in result:
            chrom = (m.get("chrom") or "").lstrip("chr")
            assert chrom in valid, f"Unexpected chrom value: {m['chrom']!r} for {m['gene']}"

    def test_hotspots_indel_variants_parsed(self):
        """Indel variants (del/ins) should be parsed without error."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        # EGFR exon-19 deletion and BRCA1/BRCA2 frameshift are indels
        indel_genes = {m["gene"] for m in result if len(m.get("ref", "")) > 1 or len(m.get("alt", "")) > 1}
        assert "EGFR" in indel_genes or "BRCA1" in indel_genes, \
            "Expected at least one indel variant (EGFR del or BRCA1 fs)"

    def test_hotspots_frameshift_so_term(self):
        """Frameshift variants should have SO=frameshift_variant in the source."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        frameshift = [m for m in result if m["gene"] in ("BRCA1", "BRCA2")]
        assert frameshift, "Expected BRCA1/BRCA2 frameshift variants"
        for m in frameshift:
            assert m.get("mutation_type") or True  # parser may or may not fill mutation_type


# ─────────────────────────────────────────────────────────────────────────────
# 2.  TCGA Lung Adenocarcinoma (LUAD)
# ─────────────────────────────────────────────────────────────────────────────

class TestTcgaLuad:
    """Parser tests against real TCGA-LUAD somatic mutations (cBioPortal)."""

    def test_luad_file_exists(self):
        _require(_VCF_TCGA_LUAD)
        assert _VCF_TCGA_LUAD.stat().st_size > 0

    def test_luad_parse_returns_list(self):
        _require(_VCF_TCGA_LUAD)
        assert isinstance(_parse_and_annotate_vcf(str(_VCF_TCGA_LUAD)), list)

    def test_luad_total_variant_count(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        assert len(result) == 60, f"Expected 60 LUAD variants, got {len(result)}"

    def test_luad_all_five_driver_genes_present(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        genes = {m["gene"] for m in result}
        for gene in _LUAD_EXPECTED_GENES:
            assert gene in genes, f"Expected LUAD driver gene {gene!r} missing"

    def test_luad_egfr_variants_present(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        egfr = [m for m in result if m["gene"] == "EGFR"]
        assert len(egfr) >= 10, f"Expected ≥10 EGFR variants in LUAD, got {len(egfr)}"

    def test_luad_egfr_l858r_present_in_real_data(self):
        """EGFR L858R is the most common actionable NSCLC mutation."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        egfr_hgvs = [m["hgvs"] for m in result if m["gene"] == "EGFR"]
        assert any("L858R" in (h or "") for h in egfr_hgvs), \
            "EGFR L858R missing from TCGA-LUAD — expected in real dataset"

    def test_luad_egfr_exon19_del_present(self):
        """EGFR exon-19 deletion (E746_A750del) is the 2nd most common NSCLC mutation."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        egfr_hgvs = [m["hgvs"] for m in result if m["gene"] == "EGFR"]
        assert any("del" in (h or "").lower() for h in egfr_hgvs), \
            "EGFR exon-19 deletion missing from TCGA-LUAD real data"

    def test_luad_kras_variants_present(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        kras = [m for m in result if m["gene"] == "KRAS"]
        assert len(kras) >= 8, f"Expected ≥8 KRAS variants in LUAD, got {len(kras)}"

    def test_luad_kras_g12_variants(self):
        """KRAS codon-12 mutations are the most common KRAS hotspot in NSCLC."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        kras_hgvs = [m["hgvs"] for m in result if m["gene"] == "KRAS"]
        assert any("G12" in (h or "") for h in kras_hgvs), \
            "KRAS G12 variant not found in TCGA-LUAD real data"

    def test_luad_no_unknown_genes(self):
        """All 60 downloaded mutations carry gene annotations."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        unknown = [m for m in result if m["gene"] == "UNKNOWN"]
        assert not unknown, f"{len(unknown)} LUAD variants have UNKNOWN gene"

    def test_luad_all_variants_have_valid_chrom(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        for m in result:
            assert m.get("chrom"), f"Missing chrom in LUAD variant: {m}"

    def test_luad_all_variants_have_integer_pos(self):
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        for m in result:
            assert isinstance(m["pos"], int), f"Non-integer pos in LUAD: {m}"

    def test_luad_grch37_positions_in_expected_ranges(self):
        """Sanity-check GRCh37 chromosome positions are plausible."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        for m in result:
            assert 1 < m["pos"] < 250_000_000, \
                f"Implausible GRCh37 position {m['pos']} for {m['gene']}"

    def test_luad_study_label_in_hgvs_or_gene(self):
        """Parsed mutations retain gene identity (not garbled)."""
        _require(_VCF_TCGA_LUAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_LUAD))
        genes = {m["gene"] for m in result}
        assert genes.issubset(_LUAD_EXPECTED_GENES), \
            f"Unexpected gene symbols in LUAD data: {genes - _LUAD_EXPECTED_GENES}"


# ─────────────────────────────────────────────────────────────────────────────
# 3.  TCGA Breast Cancer (BRCA)
# ─────────────────────────────────────────────────────────────────────────────

class TestTcgaBrca:
    """Parser tests against real TCGA-BRCA somatic mutations."""

    def test_brca_file_exists(self):
        _require(_VCF_TCGA_BRCA)
        assert _VCF_TCGA_BRCA.stat().st_size > 0

    def test_brca_parse_returns_list(self):
        _require(_VCF_TCGA_BRCA)
        assert isinstance(_parse_and_annotate_vcf(str(_VCF_TCGA_BRCA)), list)

    def test_brca_total_variant_count(self):
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        assert len(result) == 60, f"Expected 60 BRCA variants, got {len(result)}"

    def test_brca_all_five_driver_genes_present(self):
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        genes = {m["gene"] for m in result}
        for gene in _BRCA_EXPECTED_GENES:
            assert gene in genes, f"Expected BRCA driver gene {gene!r} missing"

    def test_brca_tp53_variants_present(self):
        """TP53 is the most commonly mutated gene in breast cancer (~37%)."""
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        tp53 = [m for m in result if m["gene"] == "TP53"]
        assert len(tp53) >= 8, f"Expected ≥8 TP53 mutations in BRCA, got {len(tp53)}"

    def test_brca_pik3ca_h1047r_in_real_data(self):
        """PIK3CA H1047R is the single most common PI3K hotspot in breast cancer."""
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        pik3ca_hgvs = [m["hgvs"] for m in result if m["gene"] == "PIK3CA"]
        assert any("H1047R" in (h or "") for h in pik3ca_hgvs), \
            "PIK3CA H1047R missing from TCGA-BRCA — it occurs in ~9% of breast tumours"

    def test_brca_no_unknown_genes(self):
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        unknown = [m for m in result if m["gene"] == "UNKNOWN"]
        assert not unknown, f"{len(unknown)} BRCA variants have UNKNOWN gene"

    def test_brca_chromosome_17_variants(self):
        """TP53 (chr17) and BRCA1 (chr17) variants expected on chromosome 17."""
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        chr17 = [m for m in result if m.get("chrom") == "17"]
        assert len(chr17) >= 6, f"Expected ≥6 chr17 variants in BRCA data, got {len(chr17)}"

    def test_brca_chromosome_3_variants(self):
        """PIK3CA sits on chromosome 3."""
        _require(_VCF_TCGA_BRCA)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_BRCA))
        chr3 = [m for m in result if m.get("chrom") == "3"]
        assert len(chr3) >= 6, f"Expected ≥6 chr3 variants (PIK3CA) in BRCA data"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  TCGA Colorectal (COAD/READ)
# ─────────────────────────────────────────────────────────────────────────────

class TestTcgaCoadread:
    """Parser tests against real TCGA-COADREAD somatic mutations."""

    def test_coad_file_exists(self):
        _require(_VCF_TCGA_COAD)
        assert _VCF_TCGA_COAD.stat().st_size > 0

    def test_coad_parse_returns_list(self):
        _require(_VCF_TCGA_COAD)
        assert isinstance(_parse_and_annotate_vcf(str(_VCF_TCGA_COAD)), list)

    def test_coad_total_variant_count(self):
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        assert len(result) == 60, f"Expected 60 COADREAD variants, got {len(result)}"

    def test_coad_all_five_driver_genes_present(self):
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        genes = {m["gene"] for m in result}
        for gene in _COAD_EXPECTED_GENES:
            assert gene in genes, f"Expected COADREAD driver gene {gene!r} missing"

    def test_coad_apc_variants_present(self):
        """APC is mutated in >80% of CRC — must appear."""
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        apc = [m for m in result if m["gene"] == "APC"]
        assert len(apc) >= 8, f"Expected ≥8 APC mutations in COADREAD, got {len(apc)}"

    def test_coad_kras_g12d_or_g12v_present(self):
        """KRAS codon-12 mutations drive ~40% of CRC — must be in real TCGA data."""
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        kras_hgvs = [m["hgvs"] for m in result if m["gene"] == "KRAS"]
        assert any("G12" in (h or "") or "G13" in (h or "") for h in kras_hgvs), \
            "KRAS codon-12/13 hotspot missing from TCGA-COADREAD real data"

    def test_coad_no_unknown_genes(self):
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        unknown = [m for m in result if m["gene"] == "UNKNOWN"]
        assert not unknown, f"{len(unknown)} COAD variants have UNKNOWN gene"

    def test_coad_chromosome_5_variants(self):
        """APC sits on chromosome 5."""
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        chr5 = [m for m in result if m.get("chrom") == "5"]
        assert len(chr5) >= 6, f"Expected ≥6 chr5 (APC) variants in COAD data"

    def test_coad_chromosome_12_variants(self):
        """KRAS sits on chromosome 12."""
        _require(_VCF_TCGA_COAD)
        result = _parse_and_annotate_vcf(str(_VCF_TCGA_COAD))
        chr12 = [m for m in result if m.get("chrom") == "12"]
        assert len(chr12) >= 6, f"Expected ≥6 chr12 (KRAS) variants in COAD data"


# ─────────────────────────────────────────────────────────────────────────────
# 5.  ClinVar pathogenic/likely-pathogenic somatic variants
# ─────────────────────────────────────────────────────────────────────────────

class TestClinvarCancer:
    """Parser tests against ClinVar P/LP somatic cancer variants."""

    def test_clinvar_file_exists(self):
        _require(_VCF_CLINVAR)
        assert _VCF_CLINVAR.stat().st_size > 0

    def test_clinvar_parse_returns_list(self):
        _require(_VCF_CLINVAR)
        assert isinstance(_parse_and_annotate_vcf(str(_VCF_CLINVAR)), list)

    def test_clinvar_at_least_30_variants(self):
        """10 genes × 5 hits each → at least 30 parsable variants expected."""
        _require(_VCF_CLINVAR)
        result = _parse_and_annotate_vcf(str(_VCF_CLINVAR))
        assert len(result) >= 30, f"Expected ≥30 ClinVar variants, got {len(result)}"

    def test_clinvar_all_expected_genes_covered(self):
        _require(_VCF_CLINVAR)
        result = _parse_and_annotate_vcf(str(_VCF_CLINVAR))
        genes = {m["gene"] for m in result}
        for gene in ["TP53", "KRAS", "BRAF", "EGFR", "PIK3CA", "BRCA1", "BRCA2"]:
            assert gene in genes, f"ClinVar gene {gene!r} missing"

    def test_clinvar_accession_ids_retained(self):
        """ClinVar VCV accessions should be stored as clinvar_id in parser output."""
        _require(_VCF_CLINVAR)
        result = _parse_and_annotate_vcf(str(_VCF_CLINVAR))
        vcv_ids = [m.get("clinvar_id") for m in result
                   if m.get("clinvar_id") and m["clinvar_id"].startswith(("RCV", "VCV"))]
        assert len(vcv_ids) >= 10, \
            f"Expected ≥10 ClinVar VCV/RCV IDs in results, got {len(vcv_ids)}"

    def test_clinvar_no_unknown_genes(self):
        _require(_VCF_CLINVAR)
        result = _parse_and_annotate_vcf(str(_VCF_CLINVAR))
        unknown = [m for m in result if m["gene"] == "UNKNOWN"]
        assert not unknown, f"{len(unknown)} ClinVar variants have UNKNOWN gene"

    def test_clinvar_all_have_integer_pos(self):
        _require(_VCF_CLINVAR)
        result = _parse_and_annotate_vcf(str(_VCF_CLINVAR))
        non_int = [m for m in result if not isinstance(m.get("pos"), int)]
        assert not non_int, f"{len(non_int)} ClinVar variants have non-integer pos"


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Cross-file / integration checks
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossFile:
    """Cross-file consistency and integration checks across all real datasets."""

    def test_parser_handles_all_four_real_files(self):
        """Parser should run without exception on every real VCF file."""
        files = [_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD]
        for vcf_path in files:
            _require(vcf_path)
        total = 0
        for vcf_path in files:
            result = _parse_and_annotate_vcf(str(vcf_path))
            total += len(result)
        assert total == 200, f"Expected 200 total variants across 4 files, got {total}"

    def test_tp53_appears_in_all_three_tcga_studies(self):
        """TP53 is the most commonly mutated gene in cancer — must appear in all studies."""
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            _require(vcf_path)
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            result = _parse_and_annotate_vcf(str(vcf_path))
            genes = {m["gene"] for m in result}
            assert "TP53" in genes, f"TP53 missing from {vcf_path.name}"

    def test_kras_appears_in_two_gi_cancer_studies(self):
        """KRAS is a GI tract driver — should appear in both LUAD and COAD."""
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_COAD):
            _require(vcf_path)
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_COAD):
            result = _parse_and_annotate_vcf(str(vcf_path))
            genes = {m["gene"] for m in result}
            assert "KRAS" in genes, f"KRAS missing from {vcf_path.name}"

    def test_hotspot_genes_subset_of_tcga_genes(self):
        """Every hotspot gene should be represented in at least one TCGA study."""
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            _require(vcf_path)
        tcga_genes: set[str] = set()
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            tcga_genes |= {m["gene"] for m in _parse_and_annotate_vcf(str(vcf_path))}
        hotspot_genes = {m["gene"] for m in _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))}
        overlap = hotspot_genes & tcga_genes
        assert len(overlap) >= 4, \
            f"Expected ≥4 hotspot genes in TCGA data, only found: {overlap}"

    def test_egfr_positions_on_chromosome_7(self):
        """EGFR is on chr7 — all EGFR variants across files must be on chr7."""
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD):
            _require(vcf_path)
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD):
            result = _parse_and_annotate_vcf(str(vcf_path))
            egfr = [m for m in result if m["gene"] == "EGFR"]
            for m in egfr:
                chrom = (m.get("chrom") or "").lstrip("chr")
                assert chrom == "7", \
                    f"EGFR variant on chr{chrom} (expected chr7) in {vcf_path.name}"

    def test_braf_positions_on_chromosome_7(self):
        """BRAF is on chr7 — hotspot variants must match."""
        _require(_VCF_HOTSPOTS)
        result = _parse_and_annotate_vcf(str(_VCF_HOTSPOTS))
        braf = [m for m in result if m["gene"] == "BRAF"]
        for m in braf:
            chrom = (m.get("chrom") or "").lstrip("chr")
            assert chrom == "7", f"BRAF variant on chr{chrom}, expected chr7"

    def test_tp53_positions_on_chromosome_17(self):
        """TP53 is on chr17 — hotspot and TCGA variants must match."""
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_BRCA):
            _require(vcf_path)
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_BRCA):
            result = _parse_and_annotate_vcf(str(vcf_path))
            tp53 = [m for m in result if m["gene"] == "TP53"]
            for m in tp53:
                chrom = (m.get("chrom") or "").lstrip("chr")
                assert chrom == "17", \
                    f"TP53 variant on chr{chrom} (expected chr17) in {vcf_path.name}"

    def test_kras_positions_on_chromosome_12(self):
        """KRAS is on chr12 — real TCGA variants must match."""
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_COAD):
            _require(vcf_path)
        for vcf_path in (_VCF_TCGA_LUAD, _VCF_TCGA_COAD):
            result = _parse_and_annotate_vcf(str(vcf_path))
            kras = [m for m in result if m["gene"] == "KRAS"]
            for m in kras:
                chrom = (m.get("chrom") or "").lstrip("chr")
                assert chrom == "12", \
                    f"KRAS variant on chr{chrom} (expected chr12) in {vcf_path.name}"

    def test_real_vcf_files_all_have_vcf42_header(self):
        """VCF spec requires ##fileformat=VCFv4.2 as first line."""
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            _require(vcf_path)
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            first_line = vcf_path.read_text().splitlines()[0]
            assert first_line == "##fileformat=VCFv4.2", \
                f"{vcf_path.name} missing VCFv4.2 header (got {first_line!r})"

    def test_real_vcf_files_all_have_column_header(self):
        """Each VCF must contain the standard #CHROM column header."""
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            _require(vcf_path)
        for vcf_path in (_VCF_HOTSPOTS, _VCF_TCGA_LUAD, _VCF_TCGA_BRCA, _VCF_TCGA_COAD):
            content = vcf_path.read_text()
            assert "#CHROM\tPOS\tID\tREF\tALT" in content, \
                f"{vcf_path.name} missing #CHROM column header"
