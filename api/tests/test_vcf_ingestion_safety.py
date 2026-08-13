"""Safety properties of VCF ingestion in the genomic worker.

Found by running the production parser against the Genome in a Bottle HG002
benchmark VCF (NIST v4.2.1, GRCh38). Three properties were missing, and each
failed silently rather than raising:

  1. Multi-allelic sites were not split. ALT "GGTTT,GTTTT" was stored verbatim
     as one mutation, which matches no evidence record. 46 of 8,000 real GIAB
     records were affected. If one of the alleles is the actionable one, it is
     lost. Nothing upstream normalises; there is no bcftools norm step in
     pipeline/.
  2. FILTER was unpacked and discarded, so calls the variant caller had
     explicitly rejected (Mutect2 weak_evidence, strand_bias,
     panel_of_normals) were ingested exactly like PASS calls and could drive a
     treatment recommendation.
  3. No allele fraction was carried through, so a low-VAF deamination artefact
     and a clonal driver were indistinguishable downstream. That also meant the
     FFPE detector in services/sample_qc.py could not be applied to anything
     this parser produced.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if path not in sys.path:
        sys.path.insert(0, path)

from api.workers.genomic_worker import _parse_and_annotate_vcf  # noqa: E402

_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
_HEADER_NO_SAMPLE = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


def _write(tmp_path: Path, body: str, header: str = _HEADER) -> str:
    path = tmp_path / "variants.vcf"
    path.write_text(header + body, encoding="utf-8")
    return str(path)


class TestRejectedCallsAreNotIngested:
    """A call the caller rejected must not become a recommendation."""

    @pytest.mark.parametrize(
        "filter_value",
        ["weak_evidence", "strand_bias", "panel_of_normals", "germline",
         "strand_bias;panel_of_normals", "LowQual", "base_qual"],
    )
    def test_rejected_calls_are_dropped(self, tmp_path, filter_value):
        vcf = _write(
            tmp_path,
            f"7\t55191822\t.\tT\tG\t12\t{filter_value}\tGENE=EGFR;HGVS_C=L858R\n",
            header=_HEADER_NO_SAMPLE,
        )
        assert _parse_and_annotate_vcf(vcf) == []

    @pytest.mark.parametrize("filter_value", ["PASS", "pass", ".", ""])
    def test_accepted_filters_are_kept(self, tmp_path, filter_value):
        vcf = _write(
            tmp_path,
            f"7\t55191822\t.\tT\tG\t99\t{filter_value}\tGENE=EGFR;HGVS_C=L858R\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 1
        assert mutations[0]["filter_passed"] is True

    def test_rejected_calls_are_retrievable_when_explicitly_asked_for(self, tmp_path):
        vcf = _write(
            tmp_path,
            "7\t55191822\t.\tT\tG\t12\tweak_evidence\tGENE=EGFR;HGVS_C=L858R\n"
            "7\t55019278\t.\tG\tA\t99\tPASS\tGENE=EGFR;HGVS_C=G719S\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutations = _parse_and_annotate_vcf(vcf, include_filtered=True)
        assert len(mutations) == 2
        rejected = next(m for m in mutations if m["hgvs"] == "L858R")
        assert rejected["filter_passed"] is False
        assert rejected["filter_status"] == "weak_evidence"

    def test_the_filter_value_is_always_retained(self, tmp_path):
        """Whatever the decision, it must be inspectable rather than discarded."""
        vcf = _write(
            tmp_path,
            "7\t55019278\t.\tG\tA\t99\tPASS\tGENE=EGFR\n",
            header=_HEADER_NO_SAMPLE,
        )
        assert _parse_and_annotate_vcf(vcf)[0]["filter_status"] == "PASS"


class TestMultiAllelicSitesAreSplit:
    def test_two_alt_alleles_become_two_mutations(self, tmp_path):
        vcf = _write(
            tmp_path,
            "1\t1735008\t.\tG\tGGTTT,GTTTT\t50\tPASS\tGENE=TESTGENE\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 2
        assert {m["alt"] for m in mutations} == {"GGTTT", "GTTTT"}
        assert all(m["ref"] == "G" and m["pos"] == 1735008 for m in mutations)

    def test_no_alt_retains_a_comma(self, tmp_path):
        vcf = _write(
            tmp_path,
            "1\t100\t.\tA\tT,C,G\t50\tPASS\tGENE=TESTGENE\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 3
        assert not any("," in m["alt"] for m in mutations)

    def test_single_allele_is_unchanged(self, tmp_path):
        vcf = _write(
            tmp_path,
            "7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 1
        assert mutations[0]["alt"] == "G"


class TestAlleleFractionIsCarriedThrough:
    """Without VAF, a 2% artefact and a clonal driver look identical."""

    def test_vaf_derived_from_allelic_depths(self, tmp_path):
        vcf = _write(tmp_path, "7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\tGT:DP:AD\t0/1:100:90,10\n")
        mutation = _parse_and_annotate_vcf(vcf)[0]
        assert mutation["vaf"] == pytest.approx(0.10)
        assert mutation["depth"] == 100

    def test_explicit_af_is_preferred(self, tmp_path):
        vcf = _write(tmp_path, "7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\tGT:DP:AF\t0/1:200:0.42\n")
        mutation = _parse_and_annotate_vcf(vcf)[0]
        assert mutation["vaf"] == pytest.approx(0.42)
        assert mutation["depth"] == 200

    def test_a_low_vaf_call_is_distinguishable(self, tmp_path):
        """The property the FFPE detector needs in order to be applicable here."""
        vcf = _write(
            tmp_path,
            "7\t55191822\t.\tC\tT\t99\tPASS\tGENE=EGFR\tGT:DP:AD\t0/1:500:490,10\n"
            "7\t55019278\t.\tG\tA\t99\tPASS\tGENE=EGFR\tGT:DP:AD\t0/1:500:250,250\n",
        )
        mutations = _parse_and_annotate_vcf(vcf)
        assert mutations[0]["vaf"] == pytest.approx(0.02)
        assert mutations[1]["vaf"] == pytest.approx(0.50)

    def test_missing_format_columns_do_not_crash(self, tmp_path):
        vcf = _write(
            tmp_path,
            "7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutation = _parse_and_annotate_vcf(vcf)[0]
        assert mutation["vaf"] is None
        assert mutation["depth"] is None

    @pytest.mark.parametrize(
        "fmt, sample",
        [
            ("GT:DP:AD", "0/1:.:."),
            ("GT:DP:AD", "0/1:100:."),
            ("GT:AF", "0/1:."),
            ("GT:DP:AD", "0/1:0:0,0"),
            ("GT", "0/1"),
        ],
    )
    def test_unparseable_depth_fields_yield_none_not_an_exception(self, tmp_path, fmt, sample):
        vcf = _write(tmp_path, f"7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\t{fmt}\t{sample}\n")
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 1
        assert mutations[0]["vaf"] is None

    def test_mismatched_format_and_sample_lengths_are_ignored(self, tmp_path):
        vcf = _write(tmp_path, "7\t55191822\t.\tT\tG\t99\tPASS\tGENE=EGFR\tGT:DP:AD\t0/1:100\n")
        mutations = _parse_and_annotate_vcf(vcf)
        assert len(mutations) == 1
        assert mutations[0]["vaf"] is None


class TestExistingBehaviourIsPreserved:
    def test_annotations_still_extracted(self, tmp_path):
        vcf = _write(
            tmp_path,
            "7\t55174772\t.\tT\tG\t.\tPASS\t"
            "GENE=EGFR;HGVS_C=p.L858R;SO=missense_variant;CLINVAR_ID=CV1;COSMIC_ID=COSM1\n",
            header=_HEADER_NO_SAMPLE,
        )
        mutation = _parse_and_annotate_vcf(vcf)[0]
        assert mutation["gene"] == "EGFR"
        assert mutation["hgvs"] == "p.L858R"
        assert mutation["mutation_type"] == "missense_variant"
        assert mutation["clinvar_id"] == "CV1"
        assert mutation["cosmic_id"] == "COSM1"

    def test_missing_gene_defaults_to_unknown(self, tmp_path):
        vcf = _write(tmp_path, "1\t100\t.\tA\tT\t.\tPASS\t.\n", header=_HEADER_NO_SAMPLE)
        assert _parse_and_annotate_vcf(vcf)[0]["gene"] == "UNKNOWN"

    def test_truncated_lines_are_skipped(self, tmp_path):
        vcf = _write(tmp_path, "1\t100\t.\tA\n", header=_HEADER_NO_SAMPLE)
        assert _parse_and_annotate_vcf(vcf) == []
