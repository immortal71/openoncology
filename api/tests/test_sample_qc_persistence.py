"""The QC verdict has to survive the trip from the worker to the report.

Three separate breaks kept it from doing so, each invisible from the others:

  F9  the ingestion path carried no allele fraction, so the detector had
      nothing to read
  F10 nothing called the detector at all
  this one: there was nowhere to persist the answer and no adapter onto the
      keys the report reads, so `_format_qc` never received a dict and the
      Sample & Quality section printed "QC report not provided" as its normal
      state

These tests pin the last link: the adapter emits exactly the keys the report
consumes, and a missing verdict never renders as a passing one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.oncologist_report import _format_qc  # noqa: E402
from services.sample_qc import run_sample_qc, sample_qc_to_report_dict  # noqa: E402

_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"


def _vcf(tmp_path: Path, body: str) -> str:
    path = tmp_path / "sample.vcf"
    path.write_text(_HEADER + body, encoding="utf-8")
    return str(path)


def _clean_sample(tmp_path: Path) -> str:
    body = "".join(
        f"1\t{1000 + i * 100}\t.\tA\tG\t99\tPASS\t.\tGT:DP:AD\t0/1:200:100,100\n"
        for i in range(25)
    )
    return _vcf(tmp_path, body)


def _ffpe_sample(tmp_path: Path) -> str:
    """Low-VAF C>T throughout: the cytosine-deamination signature."""
    body = "".join(
        f"1\t{2000 + i * 100}\t.\tC\tT\t99\tPASS\t.\tGT:DP:AD\t0/1:500:490,10\n"
        for i in range(30)
    )
    return _vcf(tmp_path, body)


class TestAdapterMatchesWhatTheReportReads:
    """_format_qc reads a fixed key set. The adapter must supply it."""

    REQUIRED = {
        "qc_verdict", "tumour_purity_estimate", "ffpe_artefact_rate",
        "ffpe_suspected", "ti_tv_ratio", "median_vaf", "total_variants",
        "pass_variants", "mean_depth", "warnings",
    }

    def test_every_key_the_report_reads_is_present(self, tmp_path):
        qc = sample_qc_to_report_dict(run_sample_qc(_clean_sample(tmp_path)))
        assert self.REQUIRED <= set(qc)

    def test_the_report_renders_the_adapter_output(self, tmp_path):
        qc = sample_qc_to_report_dict(run_sample_qc(_clean_sample(tmp_path)))
        formatted = _format_qc(qc)
        assert formatted["qc_verdict"] in {"PASS", "WARN", "FAIL"}
        assert formatted["qc_verdict"] != "UNKNOWN"
        assert formatted["total_variants"] == 25

    def test_the_audit_fields_survive(self, tmp_path):
        """The score behind the flag, not just the flag."""
        qc = sample_qc_to_report_dict(run_sample_qc(_ffpe_sample(tmp_path)))
        assert "ffpe_score" in qc
        assert "ffpe_confidence" in qc
        assert "coverage_adequacy" in qc


class TestAnFFPESampleIsVisibleInTheReport:
    def test_ffpe_signal_reaches_the_rendered_section(self, tmp_path):
        qc = sample_qc_to_report_dict(run_sample_qc(_ffpe_sample(tmp_path)))
        formatted = _format_qc(qc)
        assert formatted["ffpe_suspected"] is True
        assert formatted["ffpe_artefact_rate"] > 0

    def test_a_flagged_sample_carries_warnings(self, tmp_path):
        qc = sample_qc_to_report_dict(run_sample_qc(_ffpe_sample(tmp_path)))
        assert qc["warnings"], "a flagged sample must explain itself"

    def test_clean_and_ffpe_samples_do_not_render_identically(self, tmp_path):
        """The property that was absent: they used to be indistinguishable."""
        clean = _format_qc(sample_qc_to_report_dict(run_sample_qc(_clean_sample(tmp_path))))
        ffpe_dir = tmp_path / "ffpe"
        ffpe_dir.mkdir()
        ffpe = _format_qc(sample_qc_to_report_dict(run_sample_qc(_ffpe_sample(ffpe_dir))))
        assert clean["ffpe_suspected"] != ffpe["ffpe_suspected"]


class TestMissingQCIsNotAPass:
    """NULL means not assessed. It must never read as a clean bill of health."""

    def test_absent_qc_renders_as_unknown(self):
        assert _format_qc({})["qc_verdict"] == "UNKNOWN"

    def test_absent_qc_does_not_claim_ffpe_was_ruled_out(self):
        assert _format_qc({})["ffpe_suspected"] is False
        assert _format_qc({})["ffpe_artefact_rate"] is None

    @pytest.mark.parametrize(
        "field",
        ["tumour_purity_estimate", "ffpe_artefact_rate", "ti_tv_ratio",
         "median_vaf", "total_variants", "mean_depth"],
    )
    def test_unmeasured_values_stay_none_rather_than_zero(self, field):
        """Zero is a measurement. None is the absence of one."""
        assert _format_qc({})[field] is None


class TestSubmissionCarriesTheColumn:
    def test_model_has_the_field_and_defaults_to_none(self):
        from models.submission import Submission

        assert hasattr(Submission, "sample_qc")
        assert Submission.__table__.c.sample_qc.nullable is True
