"""Unit tests for the pure sample-QC functions (api/services/sample_qc.py).

Covers the substitution-class helpers, FFPE artefact detection (the C>T
deamination signature), and coverage summarisation. All operate on plain
VariantRecord lists — no VCF file I/O, no network.
"""

from api.services.sample_qc import (
    VariantRecord,
    _is_transition,
    _is_transversion,
    _is_ct_transition,
    detect_ffpe_artefacts,
    summarise_coverage,
    estimate_tumour_purity,
)


def rec(ref: str, alt: str, vaf=0.4, depth=200, qual=100.0) -> VariantRecord:
    return VariantRecord(
        chrom="1",
        pos=1000,
        ref=ref,
        alt=alt,
        qual=qual,
        filter_status="PASS",
        vaf=vaf,
        depth=depth,
        af_info=vaf,
        raw_line="",
    )


# ── substitution class helpers ──────────────────────────────────────────────────

class TestSubstitutionClass:
    def test_transitions(self):
        for r, a in [("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")]:
            assert _is_transition(r, a) is True

    def test_transitions_are_case_insensitive(self):
        assert _is_transition("c", "t") is True

    def test_transversions(self):
        assert _is_transversion("A", "C") is True
        assert _is_transversion("C", "T") is False  # that's a transition

    def test_multibase_is_not_a_transversion(self):
        # indels (len != 1) are neither transition nor transversion
        assert _is_transversion("AT", "G") is False

    def test_ct_transition_includes_complementary_ga(self):
        assert _is_ct_transition("C", "T") is True
        assert _is_ct_transition("G", "A") is True  # complementary strand
        assert _is_ct_transition("A", "G") is False


# ── FFPE artefact detection ─────────────────────────────────────────────────────

class TestDetectFfpe:
    def test_no_snvs_is_not_flagged(self):
        report = detect_ffpe_artefacts([])
        assert report.total_snvs == 0
        assert report.is_flagged is False
        assert report.confidence == "LOW"

    def test_clean_sample_not_flagged(self):
        # Diverse transversions at healthy VAF -> no FFPE signal
        records = [rec("A", "C", vaf=0.45), rec("G", "T", vaf=0.5), rec("A", "T", vaf=0.48)]
        report = detect_ffpe_artefacts(records)
        assert report.is_flagged is False
        assert report.ffpe_score < 40

    def test_heavy_low_vaf_ct_signature_is_flagged(self):
        # Many low-VAF C>T transitions = classic FFPE deamination signature
        records = [rec("C", "T", vaf=0.03) for _ in range(40)]
        report = detect_ffpe_artefacts(records)
        assert report.ct_at_non_cpg == 40
        assert report.ct_fraction == 1.0
        assert report.is_flagged is True
        assert report.ffpe_score >= 40
        assert report.confidence in {"MEDIUM", "HIGH"}

    def test_titv_ratio_computed_when_transversions_present(self):
        records = [rec("C", "T"), rec("A", "G"), rec("A", "C")]  # 2 Ti, 1 Tv
        report = detect_ffpe_artefacts(records)
        assert report.titv_ratio == 2.0

    def test_indels_excluded_from_snv_counts(self):
        records = [rec("C", "T"), rec("ATG", "A"), rec("A", "ATG")]
        report = detect_ffpe_artefacts(records)
        assert report.total_snvs == 1  # only the C>T SNV counts


# ── coverage summary ────────────────────────────────────────────────────────────

class TestSummariseCoverage:
    def test_summary_reports_depth_stats(self):
        records = [rec("C", "T", depth=100), rec("A", "G", depth=300), rec("A", "T", depth=200)]
        summary = summarise_coverage(records)
        # mean depth of 100/200/300 = 200
        assert summary.mean_depth is not None
        assert 150 <= summary.mean_depth <= 250

    def test_empty_records_do_not_crash(self):
        summary = summarise_coverage([])
        assert summary is not None


# ── tumour purity estimation ────────────────────────────────────────────────────

class TestEstimateTumourPurity:
    def test_insufficient_data_below_five_variants(self):
        est = estimate_tumour_purity([rec("C", "T", vaf=0.4) for _ in range(3)])
        assert est.confidence == "INSUFFICIENT_DATA"
        assert est.purity_pct is None

    def test_clonal_peak_at_half_vaf_implies_full_purity(self):
        # A dominant VAF cluster at ~0.5 => diploid het in pure tumour => ~100%.
        records = [rec("C", "T", vaf=0.5) for _ in range(60)]
        est = estimate_tumour_purity(records)
        assert est.purity_pct is not None
        assert est.purity_pct >= 90  # peak_vaf ~0.5 -> purity ~1.0
        assert est.vaf_peak is not None

    def test_low_vaf_cluster_implies_low_purity(self):
        # Dominant cluster near 0.1 => purity ~20%.
        records = [rec("C", "T", vaf=0.1) for _ in range(60)]
        est = estimate_tumour_purity(records)
        assert est.purity_pct is not None
        assert est.purity_pct <= 40

    def test_larger_sample_raises_confidence(self):
        small = estimate_tumour_purity([rec("C", "T", vaf=0.4) for _ in range(10)])
        large = estimate_tumour_purity([rec("C", "T", vaf=0.4) for _ in range(60)])
        assert small.confidence == "LOW"
        assert large.confidence == "MEDIUM"
