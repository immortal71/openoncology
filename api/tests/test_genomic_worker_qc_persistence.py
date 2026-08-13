"""The genomic worker must actually write the QC verdict to the submission.

`test_sample_qc_persistence.py` pins the adapter and the renderer: given a
`SampleQCReport`, the right keys come out and a missing verdict never reads as a
passing one. It does not run the worker, so it cannot see the failure mode that
produced F10 in the first place — a control that is implemented, unit-tested and
benchmarked, and never called.

That is the whole lesson of F9/F10: validation shows a control works, only
tracing the call path shows it runs. So these tests drive `run_genomic_pipeline`
end to end, with MinIO, Nextflow and the downstream Celery task stubbed and a
real SQLite session underneath, and assert against the row the worker leaves
behind. If someone deletes the persistence line, the adapter tests stay green
and these go red.
"""
from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _load_genomic_worker():
    """Import the worker with a no-op Celery decorator, as ai_worker tests do."""
    fake_workers = types.ModuleType("workers")
    mock_celery = MagicMock()
    mock_celery.task.return_value = lambda fn: fn
    fake_workers.celery_app = mock_celery
    sys.modules.setdefault("workers", fake_workers)
    sys.modules["workers"].celery_app = mock_celery  # type: ignore[assignment]

    import workers.genomic_worker as mod  # noqa: PLC0415
    return mod


_gw = _load_genomic_worker()

from database import Base  # noqa: E402
from models.submission import Submission, SubmissionStatus  # noqa: E402
from services.oncologist_report import _format_qc  # noqa: E402
from services.sample_qc import qc_payload_for_api  # noqa: E402

_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"


def _write_vcf(tmp_path: Path, body: str, name: str = "out.vcf") -> str:
    path = tmp_path / name
    path.write_text(_HEADER + body, encoding="utf-8")
    return str(path)


def _clean_vcf(tmp_path: Path) -> str:
    """Balanced substitutions at clonal VAF — nothing for QC to complain about."""
    rows = []
    for i in range(30):
        ref, alt = ("A", "G") if i % 2 == 0 else ("A", "T")
        rows.append(f"1\t{1000 + i * 100}\t.\t{ref}\t{alt}\t99\tPASS\t.\tGT:DP:AD\t0/1:200:100,100\n")
    return _write_vcf(tmp_path, "".join(rows), "clean.vcf")


def _ffpe_vcf(tmp_path: Path) -> str:
    """Low-VAF C>T throughout: the cytosine-deamination signature FFPE leaves."""
    rows = [
        f"1\t{2000 + i * 100}\t.\tC\tT\t99\tPASS\t.\tGT:DP:AD\t0/1:500:490,10\n"
        for i in range(40)
    ]
    return _write_vcf(tmp_path, "".join(rows), "ffpe.vcf")


@pytest.fixture()
def db_sessionmaker(tmp_path):
    """A real SQLite DB with the real schema, so the JSON column is exercised."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'worker.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def run_pipeline(monkeypatch, db_sessionmaker, tmp_path):
    """Drive run_genomic_pipeline with everything external stubbed out.

    Returns a callable taking the VCF the "pipeline" produced, and giving back
    the persisted Submission row.
    """
    @contextmanager
    def _session():
        session = db_sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    fake_db_sync = types.ModuleType("workers._db_sync")
    fake_db_sync.get_sync_session = _session
    monkeypatch.setitem(sys.modules, "workers._db_sync", fake_db_sync)

    fake_ai_worker = types.ModuleType("workers.ai_worker")
    fake_ai_worker.run_ai_analysis = MagicMock()
    fake_ai_worker.run_ai_analysis.apply_async.return_value = MagicMock(id="ai-job-1")
    monkeypatch.setitem(sys.modules, "workers.ai_worker", fake_ai_worker)

    monkeypatch.setattr(_gw, "_download_from_minio", lambda *a, **k: str(tmp_path / "in.dna"))
    monkeypatch.setattr(_gw, "_upload_vcf_to_minio", lambda *a, **k: "s3/annotated.vcf")

    def _run(vcf_path: str, submission_id: str = "sub-1") -> Submission:
        monkeypatch.setattr(_gw, "_run_nextflow_pipeline", lambda *a, **k: vcf_path)

        with _session() as db:
            db.add(
                Submission(
                    id=submission_id,
                    patient_id="pt-1",
                    cancer_type="Lung Adenocarcinoma",
                    status=SubmissionStatus.queued,
                )
            )

        # No `self`: whether the task is a bound Celery task or the bare
        # function, the caller passes only the business arguments.
        _gw.run_genomic_pipeline(
            submission_id=submission_id,
            patient_id="pt-1",
            biopsy_s3_key="s3/biopsy.txt",
            dna_s3_key="s3/dna.vcf",
            cancer_type="Lung Adenocarcinoma",
        )

        with _session() as db:
            return db.get(Submission, submission_id)

    return _run


class TestTheWorkerPersistsTheVerdict:
    def test_a_verdict_is_written_at_all(self, run_pipeline, tmp_path):
        submission = run_pipeline(_clean_vcf(tmp_path))
        assert submission.sample_qc is not None, (
            "the worker ran QC but persisted nothing — this is exactly F10, where "
            "the control ran and no reader could ever see the answer"
        )
        assert submission.sample_qc["qc_verdict"] in {"PASS", "WARN", "FAIL"}

    def test_the_submission_still_advances(self, run_pipeline, tmp_path):
        """QC is advisory: it records a verdict without derailing the analysis."""
        submission = run_pipeline(_clean_vcf(tmp_path))
        assert submission.status == SubmissionStatus.awaiting_ai
        assert submission.vcf_s3_key == "s3/annotated.vcf"

    def test_the_persisted_dict_has_every_key_the_report_reads(self, run_pipeline, tmp_path):
        submission = run_pipeline(_ffpe_vcf(tmp_path))
        required = {
            "qc_verdict", "tumour_purity_estimate", "ffpe_artefact_rate",
            "ffpe_suspected", "ti_tv_ratio", "median_vaf", "total_variants",
            "pass_variants", "mean_depth", "warnings",
        }
        assert required <= set(submission.sample_qc)

    def test_the_persisted_value_survives_a_json_round_trip(self, run_pipeline, tmp_path):
        """It goes through a real JSON column, so it must contain no exotic types."""
        submission = run_pipeline(_clean_vcf(tmp_path))
        assert isinstance(submission.sample_qc, dict)
        assert isinstance(submission.sample_qc["warnings"], list)


class TestTheFFPESignalReachesTheReader:
    """The point of the whole chain: a bad sample must not look like a good one."""

    def test_an_ffpe_sample_is_flagged_in_the_persisted_row(self, run_pipeline, tmp_path):
        submission = run_pipeline(_ffpe_vcf(tmp_path))
        assert submission.sample_qc["ffpe_suspected"] is True

    def test_clean_and_ffpe_submissions_do_not_persist_identically(self, run_pipeline, tmp_path):
        clean = run_pipeline(_clean_vcf(tmp_path), submission_id="sub-clean")
        ffpe = run_pipeline(_ffpe_vcf(tmp_path), submission_id="sub-ffpe")
        assert clean.sample_qc != ffpe.sample_qc

    def test_the_flag_survives_all_the_way_into_the_rendered_section(self, run_pipeline, tmp_path):
        clean = run_pipeline(_clean_vcf(tmp_path), submission_id="sub-clean")
        ffpe = run_pipeline(_ffpe_vcf(tmp_path), submission_id="sub-ffpe")
        assert _format_qc(clean.sample_qc) != _format_qc(ffpe.sample_qc)

    def test_the_flag_survives_into_the_api_payload(self, run_pipeline, tmp_path):
        submission = run_pipeline(_ffpe_vcf(tmp_path))
        payload = qc_payload_for_api(submission.sample_qc)
        assert payload["assessed"] is True
        assert payload["ffpe_suspected"] is True


class TestFailureNeverReadsAsAPass:
    def test_qc_blowing_up_leaves_the_column_null(self, run_pipeline, monkeypatch, tmp_path):
        """A crashed check must persist nothing, not an empty passing-looking dict."""
        def _boom(_path):
            raise RuntimeError("detector exploded")

        monkeypatch.setattr("services.sample_qc.run_sample_qc", _boom)
        submission = run_pipeline(_clean_vcf(tmp_path))

        assert submission.sample_qc is None
        assert submission.status == SubmissionStatus.awaiting_ai, (
            "QC is advisory — a QC failure must not discard a real analysis"
        )

    def test_a_null_column_reports_as_not_assessed(self, run_pipeline, monkeypatch, tmp_path):
        def _boom(_path):
            raise RuntimeError("detector exploded")

        monkeypatch.setattr("services.sample_qc.run_sample_qc", _boom)
        submission = run_pipeline(_clean_vcf(tmp_path))

        payload = qc_payload_for_api(submission.sample_qc)
        assert payload["qc_verdict"] == "NOT_ASSESSED"
        assert payload["assessed"] is False
        assert payload["qc_verdict"] != "PASS"
