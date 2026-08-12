"""Integration test for workers/gdpr_worker.py's erase_patient_data.

This exercises the *real* task body against a real (temp file-based) SQLite
database -- not mocked -- because the previous coverage
(test_routes_repurposing_gdpr.py) only ever patched erase_patient_data out
entirely, which is how a real bug went unnoticed: the MinIO-key collection
referenced model fields (raw_file_key, bucket_raw/vcf/reports, vcf_key,
report_key) that don't exist on the current Submission model at all -- only
biopsy_s3_key/dna_s3_key/vcf_s3_key, all in one bucket (settings.bucket_raw).
Every call would have raised AttributeError before deleting anything.

get_sync_session is patched to point at a temp file-based SQLite DB (not
:memory:, which isn't shareable across the separate sync engine used by
Celery workers) seeded with the same rows the task itself will manipulate.
MinIO, Keycloak, and email are the only things mocked -- they're genuinely
external services.
"""

import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base
from models.patient import Patient
from models.submission import Submission, SubmissionStatus
from models.deletion_request import DeletionRequest
from workers.gdpr_worker import erase_patient_data


@pytest.fixture
def sync_db():
    """A real, temp file-based SQLite DB shared by the test and the task."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def _get_sync_session():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield SessionLocal, _get_sync_session

    engine.dispose()
    os.remove(path)


class TestErasePatientData:
    def test_deletes_patient_and_collects_real_minio_keys(self, sync_db):
        SessionLocal, get_sync_session = sync_db

        session = SessionLocal()
        patient = Patient(
            keycloak_id="kc-erase-me",
            email_hash="hash-erase-me",
            country="US",
            consent_research_sharing=True,
            data_retention_days=365,
        )
        session.add(patient)
        session.flush()

        submission = Submission(
            patient_id=patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
            biopsy_s3_key="patient-uuid/biopsy/abc.pdf",
            dna_s3_key="patient-uuid/dna/def.vcf",
            vcf_s3_key="patient-uuid/vcf/ghi.vcf",
        )
        session.add(submission)
        session.flush()

        deletion_request = DeletionRequest(
            patient_id=patient.id,
            keycloak_id=patient.keycloak_id,
            requested_at=datetime.now(timezone.utc),
            status="pending",
        )
        session.add(deletion_request)
        session.commit()
        patient_id = patient.id
        deletion_request_id = deletion_request.id
        session.close()

        with patch("workers._db_sync.get_sync_session", get_sync_session), \
             patch("workers.gdpr_worker._delete_minio_objects") as mock_delete_minio, \
             patch("workers.gdpr_worker._delete_keycloak_user") as mock_delete_kc, \
             patch("workers.gdpr_worker._get_email_from_keycloak", return_value="patient@example.com"), \
             patch("workers.gdpr_worker._send_erasure_confirmation") as mock_send_email:
            erase_patient_data.run(deletion_request_id)

        # The bug: this call used to never happen with the real keys, because
        # the attribute access on the old field names raised AttributeError
        # before minio_keys was ever populated or _delete_minio_objects called.
        assert mock_delete_minio.called
        deleted_keys = mock_delete_minio.call_args[0][0]
        assert set(deleted_keys) == {
            ("openoncology-raw", "patient-uuid/biopsy/abc.pdf"),
            ("openoncology-raw", "patient-uuid/dna/def.vcf"),
            ("openoncology-raw", "patient-uuid/vcf/ghi.vcf"),
        }

        mock_delete_kc.assert_called_once_with("kc-erase-me")
        mock_send_email.assert_called_once_with("patient@example.com")

        # Verify the DB rows are actually gone.
        verify = SessionLocal()
        assert verify.get(Patient, patient_id) is None
        assert verify.get(Submission, submission.id) is None
        req = verify.get(DeletionRequest, deletion_request_id)
        assert req.status == "complete"
        assert req.completed_at is not None
        verify.close()

    def test_missing_s3_keys_are_skipped_not_crashed(self, sync_db):
        """A submission with no files attached (e.g. still queued) must not
        raise -- the `if s.biopsy_s3_key:` guards should just skip it."""
        SessionLocal, get_sync_session = sync_db

        session = SessionLocal()
        patient = Patient(
            keycloak_id="kc-no-files",
            email_hash="hash-no-files",
            country="US",
            consent_research_sharing=True,
            data_retention_days=365,
        )
        session.add(patient)
        session.flush()

        submission = Submission(
            patient_id=patient.id,
            cancer_type="Breast cancer",
            status=SubmissionStatus.queued,
        )
        session.add(submission)
        session.flush()

        deletion_request = DeletionRequest(
            patient_id=patient.id,
            keycloak_id=patient.keycloak_id,
            requested_at=datetime.now(timezone.utc),
            status="pending",
        )
        session.add(deletion_request)
        session.commit()
        deletion_request_id = deletion_request.id
        session.close()

        with patch("workers._db_sync.get_sync_session", get_sync_session), \
             patch("workers.gdpr_worker._delete_minio_objects") as mock_delete_minio, \
             patch("workers.gdpr_worker._delete_keycloak_user"), \
             patch("workers.gdpr_worker._get_email_from_keycloak", return_value=None), \
             patch("workers.gdpr_worker._send_erasure_confirmation") as mock_send_email:
            erase_patient_data.run(deletion_request_id)

        mock_delete_minio.assert_called_once_with([])
        mock_send_email.assert_not_called()  # no email on file (unknown contact)
