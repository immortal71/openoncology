"""
A submission reaches the worker, and the worker can read what was uploaded.

Found by submitting `samples/egfr_t790m_demo.vcf` through the running API. The
chain failed at four separate points, none of which any test covered, because
nothing had ever submitted anything.

  1. `submit.py` enqueued the pipeline task before committing the transaction
     that creates the submission. The worker opens its own session and looks the
     row up by id, so it found nothing. With Celery eager, which is how
     development runs when Redis is unreachable, that is deterministic: no
     submission made in development was ever processed. In production the window
     is small and real.

  2. The worker treated a missing row as success. It logged and returned, so
     Celery marked the task succeeded and nothing retried.

  3. `sweep_stale_submissions` covered only `processing`. A submission whose task
     never started stays `queued`, which the sweeper that exists to catch stuck
     work did not look at. Between them, 1 to 3 meant a lost submission produced
     no error, no retry and no sweep.

  4. `services/storage.py` writes uploads to the local filesystem when MinIO is
     unreachable in development, and both S3 helpers in `genomic_worker` went
     straight to boto3. The API put the file on disk and the worker looked for it
     in S3.
"""
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBMIT = REPO_ROOT / "api" / "routes" / "submit.py"
WORKER = REPO_ROOT / "api" / "workers" / "genomic_worker.py"
NOTIFY = REPO_ROOT / "api" / "workers" / "notify_worker.py"


# ── 1. The row is committed before anything is told about it ─────────────────

def test_the_task_is_enqueued_after_the_commit():
    """
    Ordering, asserted on the source, because reproducing the race in a test
    means reproducing a race. The worker cannot see an uncommitted row, so the
    commit has to come first.
    """
    source = SUBMIT.read_text(encoding="utf-8")
    commit = source.index("await db.commit()")
    enqueue = source.index("run_genomic_pipeline.apply_async")
    assert commit < enqueue, (
        "the pipeline task is enqueued before the transaction commits, so a "
        "worker that starts promptly finds no submission"
    )


# ── 2 and 3. A lost submission is noticed ────────────────────────────────────

def test_a_missing_submission_is_retried_not_reported_as_success():
    source = WORKER.read_text(encoding="utf-8")
    start = source.index("Submission %s not found")
    window = source[start:start + 400]
    assert "self.retry" in window, (
        "a missing submission still returns, which marks the task succeeded"
    )


def test_the_sweeper_covers_queued_as_well_as_processing():
    """
    A submission whose task never ran is stuck in queued, not processing. The
    sweeper looked only at work that had started.
    """
    source = WORKER.read_text(encoding="utf-8")
    start = source.index("def sweep_stale_submissions")
    body = source[start:start + 1600]
    assert "SubmissionStatus.queued" in body, (
        "the stale-submission sweeper ignores queued submissions"
    )
    assert "SubmissionStatus.processing" in body


# ── 4. Upload and download agree about where files are ───────────────────────

@pytest.mark.parametrize("helper", ["_download_from_minio", "_upload_vcf_to_minio"])
def test_worker_storage_helpers_honour_the_local_fallback(helper):
    """
    `services.storage` has a documented fallback for development. A consumer
    that ignores it disagrees with the half that wrote the file.
    """
    from workers import genomic_worker

    source = inspect.getsource(getattr(genomic_worker, helper))
    assert "_use_local_storage" in source, (
        f"{helper} goes straight to boto3, so it cannot read or write what "
        "services/storage.py placed on the local filesystem"
    )


def test_the_fallback_uses_the_same_layout_as_the_uploader():
    """
    storage.py writes to `<local_root>/<bucket>/<key>`. A reader using a
    different layout fails in a way that looks like a missing upload.
    """
    from workers import genomic_worker

    download = inspect.getsource(genomic_worker._download_from_minio)
    assert "_local_root()" in download
    assert "bucket_raw" in download


# ── The notification query names a column that exists ────────────────────────

def test_the_notification_query_uses_the_current_foreign_key():
    """
    RepurposingCandidate keys off result_id. notify_worker queried
    submission_id, which the model has not had since it moved to Result as its
    parent, so every notification raised AttributeError before it could be sent:
    the analysis completed and the patient was never told.

    gdpr_worker.py carries a comment about exactly this, so the correction had
    been made once already, in one of the two places that needed it.
    """
    source = NOTIFY.read_text(encoding="utf-8")
    assert "RepurposingCandidate.submission_id" not in source, (
        "notify_worker still filters on a column the model does not have"
    )
    assert "RepurposingCandidate.result_id" in source


def test_no_module_filters_repurposing_on_submission_id():
    """The same mistake anywhere else would be equally silent."""
    offenders = []
    for path in (REPO_ROOT / "api").rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        if "RepurposingCandidate.submission_id" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"stale column reference in: {offenders}"


def test_the_repurposing_model_really_keys_off_result_id():
    """If the model moves back, the assertions above are checking the wrong thing."""
    from models.repurposing import RepurposingCandidate

    assert hasattr(RepurposingCandidate, "result_id")
    assert not hasattr(RepurposingCandidate, "submission_id")
