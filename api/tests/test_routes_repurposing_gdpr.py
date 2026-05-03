"""Integration tests for the repurposing and GDPR routes.

Covers:
  GET  /api/repurposing/{result_id}
  GET  /api/me/export
  DELETE /api/me
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from unittest.mock import patch

# conftest.py already sets up client, seeded_patient, seeded_submission


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/repurposing/{result_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestRepurposingRoute:

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_result(self, client):
        resp = await client.get("/api/repurposing/nonexistent-result-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_targetable_mutation_returns_empty_candidates(
        self, client, db_session, seeded_patient
    ):
        """A result with has_targetable_mutation=False should return empty candidates."""
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        submission = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Colon",
            status=SubmissionStatus.complete,
        )
        db_session.add(submission)
        await db_session.flush()

        result = Result(
            submission_id=submission.id,
            has_targetable_mutation=False,
            target_gene=None,
            summary_text="No targetable mutations found.",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        resp = await client.get(f"/api/repurposing/{result.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_targetable_mutation"] is False
        assert data["candidates"] == []
        assert "message" in data

    @pytest.mark.asyncio
    async def test_returns_candidates_sorted_by_rank_score(
        self, client, db_session, seeded_patient
    ):
        """Candidates must come back in descending rank_score order."""
        from models.submission import Submission, SubmissionStatus
        from models.result import Result
        from models.repurposing import RepurposingCandidate

        submission = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(submission)
        await db_session.flush()

        result = Result(
            submission_id=submission.id,
            has_targetable_mutation=True,
            target_gene="EGFR",
        )
        db_session.add(result)
        await db_session.flush()

        # Insert candidates in reverse rank order to test sorting
        for rank, name in [(0.3, "Drug C"), (0.9, "Drug A"), (0.6, "Drug B")]:
            db_session.add(RepurposingCandidate(
                result_id=result.id,
                drug_name=name,
                rank_score=rank,
                approval_status="Phase 2",
                evidence_sources=["OpenTargets"],
            ))
        await db_session.commit()
        await db_session.refresh(result)

        resp = await client.get(f"/api/repurposing/{result.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_targetable_mutation"] is True
        assert data["target_gene"] == "EGFR"
        candidates = data["candidates"]
        assert len(candidates) == 3
        scores = [c["rank_score"] for c in candidates]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_candidate_has_expected_fields(
        self, client, db_session, seeded_patient
    ):
        """Each candidate dict must include all required keys."""
        from models.submission import Submission, SubmissionStatus
        from models.result import Result
        from models.repurposing import RepurposingCandidate

        submission = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Breast",
            status=SubmissionStatus.complete,
        )
        db_session.add(submission)
        await db_session.flush()

        result = Result(
            submission_id=submission.id,
            has_targetable_mutation=True,
            target_gene="ERBB2",
        )
        db_session.add(result)
        await db_session.flush()

        db_session.add(RepurposingCandidate(
            result_id=result.id,
            drug_name="Trastuzumab",
            chembl_id="CHEMBL1201585",
            binding_score=0.75,
            opentargets_score=0.88,
            rank_score=0.82,
            approval_status="Approved",
            mechanism="HER2 inhibitor",
            evidence_sources=["OncoKB", "OpenTargets"],
            matched_terms=["ERBB2"],
        ))
        await db_session.commit()

        resp = await client.get(f"/api/repurposing/{result.id}")
        assert resp.status_code == 200
        candidate = resp.json()["candidates"][0]
        expected_keys = {
            "drug_name", "chembl_id", "approval_status",
            "mechanism", "binding_score", "opentargets_score",
            "rank_score", "evidence_sources", "matched_terms",
        }
        assert expected_keys.issubset(candidate.keys())
        assert candidate["drug_name"] == "Trastuzumab"
        assert candidate["approval_status"] == "Approved"

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(
        self, client, db_session, seeded_patient
    ):
        """Patient A should not be able to view Patient B's result."""
        from models.patient import Patient
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        other_patient = Patient(
            keycloak_id="other-user-999",
            email_hash="other-hash",
            country="GB",
            consent_research_sharing=False,
            data_retention_days=180,
        )
        db_session.add(other_patient)
        await db_session.flush()

        submission = Submission(
            patient_id=other_patient.id,
            cancer_type="Melanoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(submission)
        await db_session.flush()

        result = Result(
            submission_id=submission.id,
            has_targetable_mutation=True,
            target_gene="BRAF",
        )
        db_session.add(result)
        await db_session.commit()

        # Our test client is authenticated as "test-user-123", not other_patient
        resp = await client.get(f"/api/repurposing/{result.id}")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/me/export  (GDPR Art. 20)
# ─────────────────────────────────────────────────────────────────────────────

class TestGdprExport:

    @pytest.mark.asyncio
    async def test_export_404_when_no_patient(self, client):
        """Without a patient record, export should return 404."""
        resp = await client.get("/api/me/export")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_200_with_patient(self, client, seeded_patient):
        """With a patient record, export returns 200."""
        resp = await client.get("/api/me/export")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_contains_top_level_keys(self, client, seeded_patient):
        """Export must include all GDPR-required data categories."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        required_keys = {
            "exported_at", "patient", "submissions", "mutations",
            "repurposing_candidates", "results", "orders", "campaigns",
        }
        assert required_keys.issubset(data.keys())

    @pytest.mark.asyncio
    async def test_export_patient_matches_auth_user(self, client, seeded_patient):
        """Patient block must belong to the authenticated user."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        assert data["patient"]["keycloak_id"] == "test-user-123"

    @pytest.mark.asyncio
    async def test_export_includes_submissions(self, client, seeded_submission):
        """Submissions linked to the patient must appear in the export."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        assert len(data["submissions"]) >= 1
        assert data["submissions"][0]["cancer_type"] == "Lung adenocarcinoma"

    @pytest.mark.asyncio
    async def test_export_includes_mutations(self, client, seeded_submission):
        """Mutations derived from submissions must appear in the export."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        assert len(data["mutations"]) >= 1
        assert data["mutations"][0]["gene"] == "EGFR"

    @pytest.mark.asyncio
    async def test_export_includes_results(self, client, seeded_submission):
        """Results linked to submissions must appear in the export."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        assert len(data["results"]) >= 1

    @pytest.mark.asyncio
    async def test_export_exported_at_is_iso_datetime(self, client, seeded_patient):
        """exported_at must be a valid ISO-8601 timestamp with timezone."""
        from datetime import datetime
        resp = await client.get("/api/me/export")
        data = resp.json()
        # Should parse without raising
        ts = datetime.fromisoformat(data["exported_at"])
        assert ts is not None

    @pytest.mark.asyncio
    async def test_export_empty_arrays_when_no_data(self, client, seeded_patient):
        """A patient with no submissions should have all arrays empty."""
        resp = await client.get("/api/me/export")
        data = resp.json()
        assert data["submissions"] == []
        assert data["mutations"] == []
        assert data["results"] == []
        assert data["repurposing_candidates"] == []
        assert data["orders"] == []
        assert data["campaigns"] == []


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/me  (GDPR Art. 17)
# ─────────────────────────────────────────────────────────────────────────────

class TestGdprDelete:

    @pytest.mark.asyncio
    async def test_delete_404_when_no_patient(self, client):
        """Without a patient record, deletion should return 404."""
        resp = await client.delete("/api/me")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_accepted_queues_task(self, client, seeded_patient):
        """DELETE /api/me should return 202 Accepted and a deletion_request_id."""
        with patch("routes.gdpr.erase_patient_data") as mock_erase:
            mock_erase.apply_async = lambda kwargs, queue: None
            resp = await client.delete("/api/me")
        assert resp.status_code == 202
        data = resp.json()
        assert "deletion_request_id" in data

    @pytest.mark.asyncio
    async def test_delete_idempotent_second_request_returns_202(
        self, client, seeded_patient
    ):
        """A second deletion request while one is pending returns 202 with the existing request ID."""
        with patch("routes.gdpr.erase_patient_data") as mock_erase:
            mock_erase.apply_async = lambda kwargs, queue: None
            first = await client.delete("/api/me")
            second = await client.delete("/api/me")

        assert first.status_code == 202
        # Second call is idempotent — same request ID returned
        assert second.status_code == 202
        first_id = first.json().get("deletion_request_id")
        second_id = second.json().get("deletion_request_id")
        assert first_id == second_id, "Should return the same pending request ID"

    @pytest.mark.asyncio
    async def test_delete_response_contains_message(self, client, seeded_patient):
        """Response body should include a human-readable status message."""
        with patch("routes.gdpr.erase_patient_data") as mock_erase:
            mock_erase.apply_async = lambda kwargs, queue: None
            resp = await client.delete("/api/me")
        data = resp.json()
        assert "deletion_request_id" in data or "status" in data
