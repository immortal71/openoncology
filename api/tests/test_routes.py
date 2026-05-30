"""Integration tests for the FastAPI route layer.

Covers:
  - GET /api/auth/me  (auth route)
  - GET /api/results/{id}  — 200 when submission exists and belongs to patient
  - GET /api/results/{id}  — 404 when submission not found
  - GET /api/results/{id}  — pending status returns processing message
  - GET /api/results/{id}  — 404 when submission belongs to different patient
  - GET /api/submit/       — 405 on GET (only POST allowed)
  - POST /api/submit/      — 404 when patient profile not found
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import AsyncClient


# ── /api/auth/me ──────────────────────────────────────────────────────────────

class TestAuthMe:
    async def test_returns_patient_identity(self, client: AsyncClient):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "test-user-123"
        assert body["email"] == "patient@test.openoncology.local"
        assert body["name"] == "Test Patient"
        assert "patient" in body["roles"]

    async def test_returns_roles_list(self, client: AsyncClient):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer test-token"},
        )
        assert isinstance(resp.json()["roles"], list)


# ── /api/results/{id} ────────────────────────────────────────────────────────

class TestGetResults:
    async def test_complete_submission_returns_200(
        self, client: AsyncClient, seeded_submission
    ):
        resp = await client.get(
            f"/api/results/{seeded_submission.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200

    async def test_complete_submission_body_shape(
        self, client: AsyncClient, seeded_submission
    ):
        resp = await client.get(
            f"/api/results/{seeded_submission.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        body = resp.json()
        assert body["submission_id"] == seeded_submission.id
        assert body["status"] == "complete"
        assert body["cancer_type"] == "Lung adenocarcinoma"
        assert body["has_targetable_mutation"] is True
        assert body["target_gene"] == "EGFR"

    async def test_mutations_list_populated(
        self, client: AsyncClient, seeded_submission
    ):
        resp = await client.get(
            f"/api/results/{seeded_submission.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        body = resp.json()
        assert len(body["mutations"]) >= 1
        m = body["mutations"][0]
        assert m["gene"] == "EGFR"
        assert m["hgvs"] == "p.L858R"

    async def test_unknown_submission_returns_404(self, client: AsyncClient):
        resp = await client.get(
            "/api/results/nonexistent-id-00000",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "not_found"
        assert "request_id" in body

    async def test_pending_submission_returns_processing_status(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.submission import Submission, SubmissionStatus

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Breast cancer",
            status=SubmissionStatus.processing,
        )
        db_session.add(sub)
        await db_session.commit()

        resp = await client.get(
            f"/api/results/{sub.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"

    async def test_other_patients_submission_returns_404(
        self, client: AsyncClient, db_session
    ):
        """Submission owned by another patient must not be visible."""
        from models.patient import Patient
        from models.submission import Submission, SubmissionStatus

        other = Patient(
            keycloak_id="other-user-999",
            email_hash="other-hash-999",
            country="DE",
            consent_research_sharing=False,
            data_retention_days=30,
        )
        db_session.add(other)
        await db_session.flush()

        sub = Submission(
            patient_id=other.id,
            cancer_type="Melanoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.commit()

        resp = await client.get(
            f"/api/results/{sub.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "not_found"
        assert "request_id" in body

    async def test_custom_drug_possible_when_target_gene_set(
        self, client: AsyncClient, seeded_submission
    ):
        resp = await client.get(
            f"/api/results/{seeded_submission.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        body = resp.json()
        assert body["custom_drug_possible"] is True
        assert body["custom_drug_reason"] == "target_gene_available"


# ── /api/submit/ ─────────────────────────────────────────────────────────────

class TestSubmitRoute:
    async def test_get_method_not_allowed(self, client: AsyncClient):
        resp = await client.get(
            "/api/submit/",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 405

    async def test_post_without_patient_profile_returns_404(
        self, client: AsyncClient
    ):
        """If the patient row doesn't exist for the authenticated user, return 404.

        Note: _clean_tables autouse fixture wipes all rows before every test,
        so no patient with keycloak_id='test-user-123' exists here.
        """
        import io

        resp = await client.post(
            "/api/submit/",
            headers={"Authorization": "Bearer test-token"},
            files={
                "biopsy_file": ("report.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"),
                "dna_file": ("dna.vcf", io.BytesIO(b"##VCF\n"), "text/plain"),
            },
            data={"cancer_type": "Lung adenocarcinoma"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "not_found"
        assert "request_id" in body

    async def test_post_with_valid_patient_returns_202(
        self, client: AsyncClient, seeded_patient, monkeypatch
    ):
        """With a seeded patient row and mocked storage + Celery, expect 202."""
        import io

        # Mock out heavy dependencies (upload_encrypted_file is async)
        async def _fake_upload(**kwargs):
            return f"mock/{kwargs['file_type']}.bin"

        monkeypatch.setattr(
            "routes.submit.upload_encrypted_file",
            _fake_upload,
        )

        class _FakeJob:
            id = "celery-job-id-test"

        monkeypatch.setattr(
            "routes.submit.run_genomic_pipeline.apply_async",
            lambda args, queue: _FakeJob(),
        )

        resp = await client.post(
            "/api/submit/",
            headers={"Authorization": "Bearer test-token"},
            files={
                "biopsy_file": ("biopsy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"),
                "dna_file": ("sample.vcf", io.BytesIO(b"##VCF\nchr1\t1\t.\tA\tT\t.\t.\t."), "text/plain"),
            },
            data={"cancer_type": "Lung adenocarcinoma"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "submission_id" in body

    async def test_invalid_biopsy_type_returns_422(
        self, client: AsyncClient, seeded_patient
    ):
        import io

        resp = await client.post(
            "/api/submit/",
            headers={"Authorization": "Bearer test-token"},
            files={
                "biopsy_file": ("data.exe", io.BytesIO(b"MZ"), "application/octet-stream"),
                "dna_file": ("sample.vcf", io.BytesIO(b"##VCF"), "text/plain"),
            },
            data={"cancer_type": "Melanoma"},
        )
        assert resp.status_code == 422
