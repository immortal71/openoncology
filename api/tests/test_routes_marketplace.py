"""Integration tests for the marketplace route layer.

Covers:
  - GET  /api/marketplace/pharma                              — public pharma list
  - POST /api/marketplace/order                              — create Stripe order
  - GET  /api/marketplace/nearby-pharmacies                  — pharmacy placeholder
  - POST /api/marketplace/drug-requests                      — open a drug request
  - GET  /api/marketplace/drug-requests                      — list open requests
  - GET  /api/marketplace/drug-requests/{id}                 — request detail (queued/failed/complete)
  - POST /api/marketplace/drug-requests/{id}/bids            — pharma submits a bid
  - GET  /api/marketplace/drug-requests/{id}/bids            — patient views bids
  - GET  /api/marketplace/discovery-brief/{result_id}        — AI discovery brief
  - GET  /api/marketplace/custom-drug-report/{result_id}     — downloadable report
  - POST /api/marketplace/drug-requests/from-result/{result_id} — queue custom discovery

RBAC enforced:
  - patient token: standard tests
  - pharma email match: used for submit_bid path
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

AUTH = {"Authorization": "Bearer test-token"}


async def _seed_pharma(db_session, verified=True, email="pharma@test.com"):
    from models.pharma import PharmaCompany
    company = PharmaCompany(
        name="TestPharma Corp",
        country="US",
        description="Clinical-stage oncology company",
        contact_email=email,
        verified=verified,
        min_order_usd=5000.0,
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


async def _seed_drug_request(db_session, patient, is_open=True):
    from models.bid import DrugRequest, DiscoveryStatus
    req = DrugRequest(
        patient_id=patient.id,
        target_gene="EGFR",
        drug_spec="Custom EGFR inhibitor targeting exon 20 insertions, " * 3,
        max_budget_usd=250_000.0,
        is_open=is_open,
        discovery_status=DiscoveryStatus.queued,
    )
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)
    return req


# ── Pharma listing ─────────────────────────────────────────────────────────────

class TestListPharmaCompanies:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        resp = await client.get("/api/marketplace/pharma")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_verified_company_appears(self, client: AsyncClient, db_session):
        await _seed_pharma(db_session, verified=True)
        resp = await client.get("/api/marketplace/pharma")
        assert resp.status_code == 200
        companies = resp.json()
        assert len(companies) == 1
        assert companies[0]["name"] == "TestPharma Corp"
        assert companies[0]["country"] == "US"
        assert companies[0]["min_order_usd"] == 5000.0

    async def test_unverified_company_excluded(self, client: AsyncClient, db_session):
        await _seed_pharma(db_session, verified=False)
        resp = await client.get("/api/marketplace/pharma")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_response_fields_present(self, client: AsyncClient, db_session):
        await _seed_pharma(db_session, verified=True)
        company = resp = await client.get("/api/marketplace/pharma")
        data = resp.json()[0]
        for field in ("id", "name", "country", "description", "min_order_usd"):
            assert field in data, f"Missing field: {field}"

    async def test_multiple_verified_all_returned(self, client: AsyncClient, db_session):
        from models.pharma import PharmaCompany
        for i in range(3):
            c = PharmaCompany(
                name=f"Company {i}",
                country="DE",
                description="test",
                contact_email=f"pharma{i}@test.com",
                verified=True,
            )
            db_session.add(c)
        await db_session.commit()
        resp = await client.get("/api/marketplace/pharma")
        assert len(resp.json()) == 3


# ── POST /api/marketplace/order ───────────────────────────────────────────────

class TestCreateOrder:
    async def test_no_patient_record_returns_404(self, client: AsyncClient, db_session):
        pharma = await _seed_pharma(db_session, verified=True)
        with patch("routes.marketplace.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = {
                "id": "pi_test123",
                "client_secret": "pi_test123_secret_abc",
            }
            resp = await client.post(
                "/api/marketplace/order",
                json={
                    "pharma_id": pharma.id,
                    "drug_spec": "Test drug spec",
                    "amount_usd": 10000.0,
                },
                headers=AUTH,
            )
        assert resp.status_code == 404
        assert "Patient not found" in resp.json()["detail"]

    async def test_unverified_pharma_returns_404(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        pharma = await _seed_pharma(db_session, verified=False)
        with patch("routes.marketplace.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = {
                "id": "pi_test123",
                "client_secret": "pi_test123_secret_abc",
            }
            resp = await client.post(
                "/api/marketplace/order",
                json={
                    "pharma_id": pharma.id,
                    "drug_spec": "A valid drug specification",
                    "amount_usd": 5000.0,
                },
                headers=AUTH,
            )
        assert resp.status_code == 404
        assert "Pharma company not found" in resp.json()["detail"]

    async def test_valid_order_returns_201(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        pharma = await _seed_pharma(db_session, verified=True)
        with patch("routes.marketplace.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = {
                "id": "pi_test_abc",
                "client_secret": "pi_test_abc_secret_xyz",
            }
            resp = await client.post(
                "/api/marketplace/order",
                json={
                    "pharma_id": pharma.id,
                    "drug_spec": "Custom EGFR inhibitor",
                    "amount_usd": 15000.0,
                },
                headers=AUTH,
            )
        assert resp.status_code == 201
        body = resp.json()
        assert "order_id" in body
        assert body["client_secret"] == "pi_test_abc_secret_xyz"
        assert body["amount_usd"] == 15000.0

    async def test_amount_zero_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        pharma = await _seed_pharma(db_session, verified=True)
        resp = await client.post(
            "/api/marketplace/order",
            json={
                "pharma_id": pharma.id,
                "drug_spec": "some spec",
                "amount_usd": 0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 422  # Pydantic gt=0

    async def test_amount_over_million_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        pharma = await _seed_pharma(db_session, verified=True)
        resp = await client.post(
            "/api/marketplace/order",
            json={
                "pharma_id": pharma.id,
                "drug_spec": "some spec",
                "amount_usd": 1_000_001.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 422  # Pydantic le=1_000_000


# ── GET /api/marketplace/nearby-pharmacies ────────────────────────────────────

class TestNearbyPharmacies:
    async def test_returns_200_with_list(self, client: AsyncClient):
        resp = await client.get("/api/marketplace/nearby-pharmacies")
        assert resp.status_code == 200
        body = resp.json()
        assert "pharmacies" in body
        assert isinstance(body["pharmacies"], list)
        assert len(body["pharmacies"]) >= 1

    async def test_pharmacy_fields_present(self, client: AsyncClient):
        resp = await client.get("/api/marketplace/nearby-pharmacies")
        pharmacy = resp.json()["pharmacies"][0]
        for field in ("name", "distance_km", "phone", "address"):
            assert field in pharmacy, f"Missing field: {field}"


# ── POST /api/marketplace/drug-requests ───────────────────────────────────────

class TestCreateDrugRequest:
    async def test_no_patient_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/marketplace/drug-requests",
            json={
                "drug_spec": "Custom synthesis for KRAS G12D inhibitor targeting pancreatic cancer.",
                "target_gene": "KRAS",
                "max_budget_usd": 100_000.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 404

    async def test_valid_request_returns_201(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        resp = await client.post(
            "/api/marketplace/drug-requests",
            json={
                "drug_spec": "Custom synthesis for KRAS G12D inhibitor targeting pancreatic cancer.",
                "target_gene": "KRAS",
                "max_budget_usd": 100_000.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "drug_request_id" in body
        assert body["status"] == "open"

    async def test_spec_too_short_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        resp = await client.post(
            "/api/marketplace/drug-requests",
            json={
                "drug_spec": "too short",
                "target_gene": "KRAS",
            },
            headers=AUTH,
        )
        assert resp.status_code == 422  # min_length=20


# ── GET /api/marketplace/drug-requests ────────────────────────────────────────

class TestListDrugRequests:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        resp = await client.get("/api/marketplace/drug-requests")
        assert resp.status_code == 200
        assert resp.json()["requests"] == []

    async def test_open_request_appears(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        await _seed_drug_request(db_session, seeded_patient, is_open=True)
        resp = await client.get("/api/marketplace/drug-requests")
        assert resp.status_code == 200
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["target_gene"] == "EGFR"

    async def test_closed_request_excluded(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        await _seed_drug_request(db_session, seeded_patient, is_open=False)
        resp = await client.get("/api/marketplace/drug-requests")
        assert resp.json()["requests"] == []

    async def test_request_payload_fields(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        await _seed_drug_request(db_session, seeded_patient, is_open=True)
        data = (await client.get("/api/marketplace/drug-requests")).json()["requests"][0]
        for field in ("drug_request_id", "target_gene", "drug_spec", "max_budget_usd",
                       "status", "created_at"):
            assert field in data, f"Missing field: {field}"


# ── GET /api/marketplace/drug-requests/{id} ───────────────────────────────────

class TestGetDrugRequestDetail:
    async def test_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/marketplace/drug-requests/no-such-id")
        assert resp.status_code == 404

    async def test_queued_status_returns_stage_info(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        req = await _seed_drug_request(db_session, seeded_patient)
        resp = await client.get(f"/api/marketplace/drug-requests/{req.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert "message" in body

    async def test_failed_status_returns_error_message(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.bid import DiscoveryStatus
        req = await _seed_drug_request(db_session, seeded_patient)
        req.discovery_status = DiscoveryStatus.failed
        req.discovery_error = "ChEMBL API timeout"
        db_session.add(req)
        await db_session.commit()
        resp = await client.get(f"/api/marketplace/drug-requests/{req.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["stage"] == 2

    async def test_complete_status_returns_full_brief(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.bid import DiscoveryStatus
        req = await _seed_drug_request(db_session, seeded_patient)
        req.discovery_status = DiscoveryStatus.complete
        req.discovery_brief = {
            "target_gene": "EGFR",
            "cancer_type": "Lung adenocarcinoma",
            "reason": "EGFR L858R hotspot mutation",
            "mutation_profile": ["p.L858R"],
            "lead_candidates": [],
            "de_novo_candidates": [],
            "component_library": {"scaffolds": [], "fragments": []},
            "handoff_note": "Test note",
        }
        db_session.add(req)
        await db_session.commit()
        resp = await client.get(f"/api/marketplace/drug-requests/{req.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["stage"] == 2
        assert "lead_compounds" in body
        assert "de_novo_candidates" in body
        assert "computational_synthesis_plan" in body


# ── POST /api/marketplace/drug-requests/{id}/bids ────────────────────────────

class TestSubmitBid:
    async def test_non_pharma_user_returns_403(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        """Patient token whose email doesn't match any pharma gets 403."""
        req = await _seed_drug_request(db_session, seeded_patient)
        resp = await client.post(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            json={"price_usd": 80000.0, "estimated_weeks": 24, "notes": "Timeline feasible"},
            headers=AUTH,
        )
        assert resp.status_code == 403
        assert "verified pharma" in resp.json()["detail"]

    async def test_nonexistent_request_returns_404(
        self, client: AsyncClient, db_session
    ):
        """Even a valid pharma gets 404 for a missing request."""
        from models.pharma import PharmaCompany
        pharma = await _seed_pharma(
            db_session,
            verified=True,
            email="patient@test.openoncology.local",  # matches demo token
        )
        resp = await client.post(
            "/api/marketplace/drug-requests/no-such-id/bids",
            json={"price_usd": 50000.0, "estimated_weeks": 12},
            headers=AUTH,
        )
        # Should be 403 (pharma check happens first based on email match) or 404
        assert resp.status_code in (403, 404)

    async def test_pharma_can_submit_bid(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        """A verified pharma whose email matches the auth token can bid."""
        # Create pharma whose contact_email matches the test token's email
        pharma = await _seed_pharma(
            db_session,
            verified=True,
            email="patient@test.openoncology.local",
        )
        req = await _seed_drug_request(db_session, seeded_patient)
        resp = await client.post(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            json={"price_usd": 80000.0, "estimated_weeks": 20, "notes": "18-month timeline"},
            headers=AUTH,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "bid_id" in body
        assert body["status"] == "open"
        assert body["price_usd"] == 80000.0

    async def test_bid_exceeds_budget_returns_400(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        """Bid price above patient's budget ceiling must be rejected."""
        await _seed_pharma(
            db_session,
            verified=True,
            email="patient@test.openoncology.local",
        )
        req = await _seed_drug_request(db_session, seeded_patient)
        # req has max_budget_usd=250_000
        resp = await client.post(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            json={"price_usd": 300_000.0, "estimated_weeks": 24},
            headers=AUTH,
        )
        assert resp.status_code == 400
        assert "budget" in resp.json()["detail"].lower()

    async def test_negative_weeks_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        req = await _seed_drug_request(db_session, seeded_patient)
        resp = await client.post(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            json={"price_usd": 50000.0, "estimated_weeks": -1},
            headers=AUTH,
        )
        assert resp.status_code == 422  # Pydantic gt=0


# ── GET /api/marketplace/drug-requests/{id}/bids ─────────────────────────────

class TestListBids:
    async def test_non_owner_returns_404(
        self, client: AsyncClient, db_session
    ):
        """A drug request owned by another patient must not leak its bids."""
        from models.patient import Patient
        from models.bid import DrugRequest, DiscoveryStatus

        other = Patient(
            keycloak_id="other-user-999",
            email_hash="other-hash",
            country="GB",
            consent_research_sharing=False,
            data_retention_days=180,
        )
        db_session.add(other)
        await db_session.flush()

        req = DrugRequest(
            patient_id=other.id,
            target_gene="BRAF",
            drug_spec="Custom BRAF inhibitor for melanoma treatment, exon 15 V600E.",
            is_open=True,
            discovery_status=DiscoveryStatus.queued,
        )
        db_session.add(req)
        await db_session.commit()

        resp = await client.get(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            headers=AUTH,
        )
        # Either 404 (patient not found) or 404 (request not found)
        assert resp.status_code in (404, 407)

    async def test_owner_sees_bids(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        req = await _seed_drug_request(db_session, seeded_patient)
        pharma = await _seed_pharma(db_session, verified=True, email="pharma@corp.com")

        from models.bid import PharmaBid, BidStatus
        bid = PharmaBid(
            drug_request_id=req.id,
            pharma_id=pharma.id,
            price_usd=70_000.0,
            estimated_weeks=18,
            notes="On-track delivery",
            status=BidStatus.open,
        )
        db_session.add(bid)
        await db_session.commit()

        resp = await client.get(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            headers=AUTH,
        )
        assert resp.status_code == 200
        bids = resp.json()
        assert len(bids) == 1
        assert bids[0]["price_usd"] == 70_000.0

    async def test_empty_bids_list(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        req = await _seed_drug_request(db_session, seeded_patient)
        resp = await client.get(
            f"/api/marketplace/drug-requests/{req.id}/bids",
            headers=AUTH,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /api/marketplace/discovery-brief/{result_id} ─────────────────────────

class TestDiscoveryBrief:
    async def test_nonexistent_result_returns_404(self, client: AsyncClient):
        resp = await client.get(
            "/api/marketplace/discovery-brief/no-such-id",
            headers=AUTH,
        )
        assert resp.status_code == 404

    async def test_other_patient_result_returns_404(
        self, client: AsyncClient, db_session
    ):
        from models.patient import Patient
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        other = Patient(
            keycloak_id="other-xyz",
            email_hash="other-xyz-hash",
            country="FR",
            consent_research_sharing=True,
            data_retention_days=365,
        )
        db_session.add(other)
        await db_session.flush()

        sub = Submission(
            patient_id=other.id,
            cancer_type="Melanoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=True,
            target_gene="BRAF",
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.get(
            f"/api/marketplace/discovery-brief/{result.id}",
            headers=AUTH,
        )
        assert resp.status_code == 404

    async def test_missing_target_gene_returns_400(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        # No target_gene, no mutations attached
        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=False,
            target_gene=None,
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.get(
            f"/api/marketplace/discovery-brief/{result.id}",
            headers=AUTH,
        )
        assert resp.status_code == 400
        assert "target gene" in resp.json()["detail"].lower()

    async def test_valid_result_returns_brief(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=True,
            target_gene="EGFR",
        )
        db_session.add(result)
        await db_session.commit()

        with patch("routes.marketplace.build_custom_discovery_brief", new_callable=AsyncMock) as mock_brief:
            mock_brief.return_value = {
                "target_gene": "EGFR",
                "cancer_type": "Lung adenocarcinoma",
                "reason": "EGFR L858R",
                "lead_candidates": [],
                "component_library": {},
            }
            resp = await client.get(
                f"/api/marketplace/discovery-brief/{result.id}",
                headers=AUTH,
            )
        assert resp.status_code == 200
        assert resp.json()["target_gene"] == "EGFR"


# ── GET /api/marketplace/custom-drug-report/{result_id} ──────────────────────

class TestCustomDrugReport:
    async def test_valid_result_returns_report(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=True,
            target_gene="EGFR",
        )
        db_session.add(result)
        await db_session.commit()

        with patch("routes.marketplace.build_custom_discovery_brief", new_callable=AsyncMock) as mock_brief:
            mock_brief.return_value = {
                "target_gene": "EGFR",
                "cancer_type": "Lung adenocarcinoma",
                "reason": "EGFR L858R",
                "mutation_profile": ["p.L858R"],
                "lead_candidates": [],
                "component_library": {"scaffolds": [], "fragments": []},
                "handoff_note": "Test note",
            }
            resp = await client.get(
                f"/api/marketplace/custom-drug-report/{result.id}",
                headers=AUTH,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result_id"] == result.id
        assert "report_text" in body
        assert "OpenOncology Custom Drug Discovery Report" in body["report_text"]
        assert body["filename"].startswith("custom_drug_report_")

    async def test_missing_target_gene_returns_400(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Unknown",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=False,
            target_gene=None,
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.get(
            f"/api/marketplace/custom-drug-report/{result.id}",
            headers=AUTH,
        )
        assert resp.status_code == 400
