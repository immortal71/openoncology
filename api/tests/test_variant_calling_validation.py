"""Properties of the variant calling validation harness.

scripts/validate_variant_calling.py is the measuring instrument for the one
analytical gate in docs/REGULATORY_FRAMEWORK.md section 3.1 that has no
measurement. A benchmark that reports the wrong number is worse than no
benchmark, because it displaces one, so the comparison engine is pinned here
rather than trusted.

The cases below are the ones where a naive implementation gets it wrong:
allele trimming, BED half-open boundaries, multi-allelic splitting, and
duplicate query records inflating the true positive count.
"""
from __future__ import annotations

import gzip
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.validate_variant_calling import (  # noqa: E402
    ConfidentRegions,
    compare,
    is_snv,
    iter_vcf_variants,
    norm_chrom,
    normalise_allele,
)

_HEADER = (
    "##fileformat=VCFv4.2\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
)


def _write_vcf(tmp_path: Path, body: str, name: str = "v.vcf", gz: bool = False) -> Path:
    path = tmp_path / (name + (".gz" if gz else ""))
    data = _HEADER + body
    if gz:
        with gzip.open(path, "wt") as fh:
            fh.write(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _rec(chrom="chr20", pos=100, ref="A", alt="G", filt="PASS", gt="0/1") -> str:
    return f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t50\t{filt}\t.\tGT\t{gt}\n"


class TestNormaliseAllele:
    def test_snv_is_unchanged(self):
        assert normalise_allele(100, "A", "G") == (100, "A", "G")

    def test_common_suffix_is_trimmed(self):
        # AGT>ACT is really G>C at the second base.
        assert normalise_allele(100, "AGT", "ACT") == (101, "G", "C")

    def test_already_minimal_insertion_is_unchanged(self):
        assert normalise_allele(100, "A", "AGG") == (100, "A", "AGG")

    def test_suffix_is_trimmed_before_prefix(self):
        # AT>ATT inserts one T. Trimming the shared suffix first yields
        # (100, A, AT); trimming the prefix first would yield (101, T, TT).
        # Both describe the same insertion, which is the homopolymer ambiguity
        # only left-alignment against the reference can settle. The order is
        # fixed here so that both sides of a comparison reduce identically.
        assert normalise_allele(100, "AT", "ATT") == (100, "A", "AT")

    def test_never_empties_an_allele(self):
        pos, ref, alt = normalise_allele(100, "AAAA", "AAAA")
        assert ref and alt

    def test_case_is_normalised(self):
        assert normalise_allele(100, "a", "g") == (100, "A", "G")

    def test_deletion_keeps_anchor_base(self):
        pos, ref, alt = normalise_allele(100, "ACCT", "ACT")
        assert len(ref) >= 1 and len(alt) >= 1
        # The same deletion written with more padding must reduce identically.
        assert (pos, ref, alt) == normalise_allele(99, "GACCT", "GACT")


class TestIsSnv:
    def test_single_base_substitution(self):
        assert is_snv("A", "G")

    def test_insertion_is_not_snv(self):
        assert not is_snv("A", "AG")

    def test_deletion_is_not_snv(self):
        assert not is_snv("AG", "A")

    def test_identity_is_not_snv(self):
        assert not is_snv("A", "A")


class TestNormChrom:
    def test_prefix_stripped(self):
        assert norm_chrom("chr20") == "20"

    def test_bare_contig_unchanged(self):
        assert norm_chrom("20") == "20"

    def test_chr_and_bare_compare_equal(self):
        assert norm_chrom("chrX") == norm_chrom("X")


class TestIterVcfVariants:
    def test_multi_allelic_record_is_split(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(ref="G", alt="GT,GTT"))
        out = list(iter_vcf_variants(path))
        assert len(out) == 2

    def test_non_pass_dropped_by_default(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(filt="weak_evidence"))
        assert list(iter_vcf_variants(path)) == []

    def test_non_pass_kept_when_requested(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(filt="weak_evidence"))
        assert len(list(iter_vcf_variants(path, pass_only=False))) == 1

    def test_dot_filter_counts_as_passing(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(filt="."))
        assert len(list(iter_vcf_variants(path))) == 1

    def test_star_allele_skipped(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(ref="A", alt="*"))
        assert list(iter_vcf_variants(path)) == []

    def test_chrom_filter_applies(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(chrom="chr1") + _rec(chrom="chr20"))
        out = list(iter_vcf_variants(path, chroms={"20"}))
        assert [r[0] for r in out] == ["20"]

    def test_gzip_is_read(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(), gz=True)
        assert len(list(iter_vcf_variants(path))) == 1

    def test_genotype_is_extracted(self, tmp_path):
        path = _write_vcf(tmp_path, _rec(gt="1|1"))
        assert list(iter_vcf_variants(path))[0][4] == "1/1"


class TestConfidentRegions:
    def _bed(self, tmp_path, text) -> Path:
        p = tmp_path / "r.bed"
        p.write_text(text, encoding="utf-8")
        return p

    def test_bed_is_half_open_zero_based(self, tmp_path):
        # BED 100-200 covers 0-based [100,200) = 1-based POS 101..200.
        regions = ConfidentRegions.from_bed(self._bed(tmp_path, "chr20\t100\t200\n"))
        assert not regions.contains("20", 100)
        assert regions.contains("20", 101)
        assert regions.contains("20", 200)
        assert not regions.contains("20", 201)

    def test_position_between_intervals_excluded(self, tmp_path):
        regions = ConfidentRegions.from_bed(
            self._bed(tmp_path, "chr20\t100\t200\nchr20\t300\t400\n")
        )
        assert not regions.contains("20", 250)
        assert regions.contains("20", 350)

    def test_unknown_contig_excluded(self, tmp_path):
        regions = ConfidentRegions.from_bed(self._bed(tmp_path, "chr20\t100\t200\n"))
        assert not regions.contains("7", 150)

    def test_overlapping_intervals_are_merged(self, tmp_path):
        regions = ConfidentRegions.from_bed(
            self._bed(tmp_path, "chr20\t100\t200\nchr20\t150\t300\n")
        )
        assert regions.interval_count() == 1
        assert regions.contains("20", 250)

    def test_out_of_order_intervals_are_sorted(self, tmp_path):
        regions = ConfidentRegions.from_bed(
            self._bed(tmp_path, "chr20\t300\t400\nchr20\t100\t200\n")
        )
        assert regions.contains("20", 150)
        assert regions.contains("20", 350)

    def test_track_lines_ignored(self, tmp_path):
        regions = ConfidentRegions.from_bed(
            self._bed(tmp_path, 'track name="x"\nchr20\t100\t200\n')
        )
        assert regions.interval_count() == 1

    def test_base_count(self, tmp_path):
        regions = ConfidentRegions.from_bed(
            self._bed(tmp_path, "chr20\t100\t200\nchr20\t300\t350\n")
        )
        assert regions.base_count() == 150


class TestCompare:
    def _v(self, pos, ref="A", alt="G", chrom="20", gt="0/1"):
        return (chrom, pos, ref, alt, gt)

    def test_perfect_agreement(self):
        truth = [self._v(100), self._v(200)]
        result = compare(iter(truth), iter(list(truth)))
        assert result["overall"]["sensitivity"] == 1.0
        assert result["overall"]["ppv"] == 1.0
        assert result["overall"]["fn"] == 0

    def test_missed_variant_is_a_false_negative(self):
        result = compare(iter([self._v(100), self._v(200)]), iter([self._v(100)]))
        assert result["overall"]["fn"] == 1
        assert result["overall"]["sensitivity"] == 0.5
        assert result["overall"]["ppv"] == 1.0

    def test_extra_variant_is_a_false_positive(self):
        result = compare(iter([self._v(100)]), iter([self._v(100), self._v(200)]))
        assert result["overall"]["fp"] == 1
        assert result["overall"]["sensitivity"] == 1.0
        assert result["overall"]["ppv"] == 0.5

    def test_duplicate_query_record_does_not_inflate_tp(self):
        result = compare(iter([self._v(100)]), iter([self._v(100), self._v(100)]))
        assert result["overall"]["tp"] == 1
        assert result["overall"]["fp"] == 1

    def test_snv_and_indel_are_stratified(self):
        truth = [self._v(100, "A", "G"), self._v(200, "A", "AGG")]
        result = compare(iter(truth), iter([self._v(100, "A", "G")]))
        assert result["snv"]["tp"] == 1
        assert result["snv"]["fn"] == 0
        assert result["indel"]["fn"] == 1
        assert result["indel"]["tp"] == 0

    def test_differently_padded_same_variant_matches(self):
        # Truth writes the deletion with one anchor base, query with two.
        truth = iter_vcf_variants
        t = [("20",) + normalise_allele(100, "GACCT", "GACT") + ("0/1",)]
        q = [("20",) + normalise_allele(101, "ACCT", "ACT") + ("0/1",)]
        result = compare(iter(t), iter(q))
        assert result["overall"]["tp"] == 1

    def test_confident_regions_exclude_both_sides(self, tmp_path):
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")
        regions = ConfidentRegions.from_bed(bed)
        # POS 150 inside, POS 500 outside on both sides.
        result = compare(
            iter([self._v(150), self._v(500)]),
            iter([self._v(150), self._v(500)]),
            regions,
        )
        assert result["overall"]["truth_total"] == 1
        assert result["overall"]["query_total"] == 1
        assert result["query_records_outside_confident_regions"] == 1

    def test_genotype_mismatch_ignored_by_default(self):
        result = compare(
            iter([self._v(100, gt="1/1")]), iter([self._v(100, gt="0/1")])
        )
        assert result["overall"]["tp"] == 1
        assert result["genotype_mismatches"] == 0

    def test_genotype_mismatch_counted_when_requested(self):
        result = compare(
            iter([self._v(100, gt="1/1")]),
            iter([self._v(100, gt="0/1")]),
            match_genotype=True,
        )
        assert result["overall"]["tp"] == 0
        assert result["overall"]["fp"] == 1
        assert result["genotype_mismatches"] == 1

    def test_chrom_prefix_does_not_prevent_a_match(self):
        result = compare(
            iter([self._v(100, chrom=norm_chrom("chr20"))]),
            iter([self._v(100, chrom=norm_chrom("20"))]),
        )
        assert result["overall"]["tp"] == 1

    def test_empty_query_gives_zero_sensitivity_and_null_ppv(self):
        result = compare(iter([self._v(100)]), iter([]))
        assert result["overall"]["sensitivity"] == 0.0
        assert result["overall"]["ppv"] is None

    def test_targets_are_evaluated(self):
        # 99 of 100 recovered is exactly the sensitivity target.
        truth = [self._v(p) for p in range(1000, 1100)]
        result = compare(iter(truth), iter(truth[:99]))
        assert result["overall"]["sensitivity"] == pytest.approx(0.99)
        assert result["overall"]["meets_sensitivity_target"] is True
        assert result["overall"]["meets_ppv_target"] is True


class TestTheHarnessCanFail:
    """What result would have falsified this?

    docs/risk_analysis.md section 7 requires that question to be answerable
    before a validation number is quoted, because F5 was a benchmark that could
    not fail. These cases reproduce defects the repository actually had and
    assert the harness reports them as loss rather than as agreement.
    """

    def test_detects_unsplit_multi_allelic_records(self, tmp_path):
        """The F8 defect: ALT stored verbatim instead of one variant per allele."""
        path = _write_vcf(tmp_path, _rec(pos=150, ref="G", alt="GT,GTT"))
        truth = list(iter_vcf_variants(path))
        assert len(truth) == 2

        # A parser with the pre-fix behaviour emits the ALT column unsplit.
        broken = [("20", 150, "G", "GT,GTT", "0/1")]
        result = compare(iter(truth), iter(broken))

        assert result["overall"]["fn"] == 2, "both real alleles must be missed"
        assert result["overall"]["fp"] == 1, "the concatenated allele is spurious"
        assert result["overall"]["sensitivity"] == 0.0

    def test_detects_dropped_records(self, tmp_path):
        """The general case: ingestion silently loses a variant."""
        body = "".join(_rec(pos=p) for p in (150, 160, 170, 180))
        path = _write_vcf(tmp_path, body)
        truth = list(iter_vcf_variants(path))
        result = compare(iter(truth), iter(truth[:3]))
        assert result["overall"]["sensitivity"] == 0.75
        assert result["overall"]["meets_sensitivity_target"] is False

    def test_gate_flag_exits_non_zero_on_failure(self, tmp_path):
        import scripts.validate_variant_calling as vv

        truth = _write_vcf(tmp_path, _rec(pos=150) + _rec(pos=160), name="t.vcf")
        query = _write_vcf(tmp_path, _rec(pos=150), name="q.vcf")
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")

        rc = vv.main(
            [
                "--query", str(query),
                "--truth", str(truth),
                "--bed", str(bed),
                "--out", str(tmp_path / "o.json"),
                "--gate",
            ]
        )
        assert rc == 1, "50% sensitivity must fail the gate"


class TestMultipleQueryFiles:
    """Callers that emit SNPs and indels separately must score as one call set.

    The NIST BGIseq GATK HaplotypeCaller release ships two VCFs per build.
    Scoring either alone would report a false negative for every variant of the
    other class.
    """

    def test_two_files_are_scored_as_one_call_set(self, tmp_path):
        import json

        import scripts.validate_variant_calling as vv

        truth = _write_vcf(
            tmp_path,
            _rec(pos=150, ref="A", alt="G") + _rec(pos=160, ref="C", alt="CTT"),
            name="truth.vcf",
        )
        snp = _write_vcf(tmp_path, _rec(pos=150, ref="A", alt="G"), name="snp.vcf")
        indel = _write_vcf(tmp_path, _rec(pos=160, ref="C", alt="CTT"), name="indel.vcf")
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")
        out = tmp_path / "o.json"

        rc = vv.main(
            [
                "--query", str(snp), str(indel),
                "--truth", str(truth),
                "--bed", str(bed),
                "--out", str(out),
            ]
        )
        assert rc == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["results"]["overall"]["tp"] == 2
        assert payload["results"]["overall"]["fn"] == 0
        assert len(payload["query"]) == 2

    def test_one_file_alone_misses_the_other_class(self, tmp_path):
        import scripts.validate_variant_calling as vv

        truth = _write_vcf(
            tmp_path,
            _rec(pos=150, ref="A", alt="G") + _rec(pos=160, ref="C", alt="CTT"),
            name="truth.vcf",
        )
        snp = _write_vcf(tmp_path, _rec(pos=150, ref="A", alt="G"), name="snp.vcf")
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")
        rc = vv.main(
            [
                "--query", str(snp),
                "--truth", str(truth),
                "--bed", str(bed),
                "--out", str(tmp_path / "o.json"),
                "--gate",
            ]
        )
        assert rc == 1, "half the truth set missing must fail the gate"

    def test_missing_query_file_is_rejected(self, tmp_path):
        import scripts.validate_variant_calling as vv

        truth = _write_vcf(tmp_path, _rec(pos=150), name="truth.vcf")
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            vv.main(
                [
                    "--query", str(tmp_path / "nope.vcf"),
                    "--truth", str(truth),
                    "--bed", str(bed),
                    "--out", str(tmp_path / "o.json"),
                ]
            )


class TestPathCoverage:
    """A perfect score over an input that exercises nothing must say so.

    The first real run of this harness scored 100% on GIAB chr20, where every
    record is PASS and none are malformed, so two of the three ingestion
    behaviours the score appears to endorse were never executed. The reporting
    below is what keeps that visible.
    """

    def test_absent_paths_are_reported_as_not_exercised(self):
        from scripts.validate_variant_calling import summarise_path_coverage

        cov = summarise_path_coverage(
            {
                "records": 100,
                "alt_alleles": 100,
                "multi_allelic_records": 5,
                "caller_rejected_records": 0,
                "malformed_records": 0,
            }
        )
        assert any("F8" in e for e in cov["exercised"])
        assert any("F7" in e for e in cov["not_exercised"])
        assert any("malformed" in e for e in cov["not_exercised"])

    def test_all_paths_exercised_leaves_nothing_unexercised(self):
        from scripts.validate_variant_calling import summarise_path_coverage

        cov = summarise_path_coverage(
            {
                "records": 100,
                "alt_alleles": 100,
                "multi_allelic_records": 5,
                "caller_rejected_records": 3,
                "malformed_records": 1,
            }
        )
        assert cov["not_exercised"] == []
        assert len(cov["exercised"]) == 3

    def test_counts_are_carried_through(self):
        from scripts.validate_variant_calling import summarise_path_coverage

        cov = summarise_path_coverage(
            {"records": 7, "multi_allelic_records": 2, "caller_rejected_records": 0}
        )
        assert cov["input"]["records"] == 7
        assert "n=2" in " ".join(cov["exercised"])
        assert "n=0" in " ".join(cov["not_exercised"])


class TestIngestionFidelityIsNotTheGate:
    """The harness must not let a mode 2 run be read as the gate.

    docs/risk_analysis.md F5 is a benchmark that could not fail being quoted as
    validation. The ingestion mode has the same shape, so the label it writes
    into the result file is pinned.
    """

    def test_result_payload_names_the_mode(self, tmp_path, monkeypatch):
        import scripts.validate_variant_calling as vv

        truth = _write_vcf(tmp_path, _rec(pos=150) + _rec(pos=160, ref="C", alt="T"))
        bed = tmp_path / "r.bed"
        bed.write_text("chr20\t100\t200\n", encoding="utf-8")
        out = tmp_path / "out.json"

        rc = vv.main(
            [
                "--query",
                str(truth),
                "--truth",
                str(truth),
                "--bed",
                str(bed),
                "--out",
                str(out),
            ]
        )
        assert rc == 0
        import json

        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["mode"] == "variant_calling"
        assert payload["results"]["overall"]["tp"] == 2
