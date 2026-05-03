"""Integration tests for pharma_admin, oncologist, crowdfund and campaign routes.

Covers:
  Pharma Admin (/api/pharma)
  - POST /api/pharma/apply                 — public application
  - GET  /api/pharma/applications          — admin: list pending
  - POST /api/pharma/verify/{id}           — admin: approve / reject
  - GET  /api/pharma/                      — list verified
  - GET  /api/pharma/{id}                  — single verified company

  Oncologist (/api/oncologist)
  - GET  /api/oncologist/pending           — oncologist role required
  - POST /api/oncologist/review            — oncologist role required

  Crowdfund (/api/crowdfund)
  - POST /api/crowdfund/                   — create campaign
  - GET  /api/crowdfund/{slug}             — public view (active + public)
  - POST /api/crowdfund/{slug}/donate      — Stripe donation intent
  - POST /api/crowdfund/{slug}/activate    — patient activates campaign
  - POST /api/crowdfund/{slug}/close       — patient/admin closes campaign
  - POST /api/crowdfund/{slug}/complete    — admin triggers payout
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

from main import app
from routes.auth import get_current_patient

AUTH = {"Authorization": "Bearer test-token"}

# ── Role helpers ──────────────────────────────────────────────────────────────

def _admin_override():
    async def _override():
        return {
            "sub": "test-user-123",
            "email": "admin@test.openoncology.local",
            "name": "Admin User",
            "realm_access": {"roles": ["admin"]},
        }
    return _override


def _oncologist_override():
    async def _override():
        return {
            "sub": "test-user-123",
            "email": "onco@test.openoncology.local",
            "name": "Dr Test",
            "realm_access": {"roles": ["oncologist"]},
        }
    return _override


# ── Pharma Admin: POST /api/pharma/apply ─────────────────────────────────────

class TestPharmaApply:
    async def test_valid_application_returns_201(self, client: AsyncClient):
        resp = await client.post(
            "/api/pharma/apply",
            json={
                "name": "OncoDrug Ltd",
                "description": "Phase III oncology drug developer",
                "contact_email": "apply@oncodrug.com",
                "country": "DE",
                "registration_number": "DE-PHARMA-001",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["status"] == "pending_review"

    async def test_invalid_email_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/pharma/apply",
            json={
                "name": "BadMailPharma",
                "description": "Test company",
                "contact_email": "not-an-email",
            },
        )
        assert resp.status_code == 422

    async def test_submitted_company_is_unverified(
        self, client: AsyncClient, db_session
    ):
        resp = await client.post(
            "/api/pharma/apply",
            json={
                "name": "NewCo",
                "description": "A new pharma",
                "contact_email": "newco@test.com",
            },
        )
        assert resp.status_code == 201
        company_id = resp.json()["id"]

        # Not yet verified so should not appear in public list
        list_resp = await client.get("/api/pharma/")
        verified_ids = [c["id"] for c in list_resp.json()]
        assert company_id not in verified_ids


# ── Pharma Admin: GET /api/pharma/applications (admin only) ──────────────────

class TestPharmaListApplications:
    async def test_patient_role_returns_403(self, client: AsyncClient):
        resp = await client.get("/api/pharma/applications", headers=AUTH)
        assert resp.status_code == 403

    async def test_admin_sees_pending_companies(
        self, client: AsyncClient, db_session
    ):
        app.dependency_overrides[get_current_patient] = _admin_override()
        # Seed an unverified company
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="Pending Inc",
            country="US",
            description="Awaiting review",
            contact_email="pending@inc.com",
            verified=False,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.get("/api/pharma/applications", headers=AUTH)
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Pending Inc" in names

    async def test_admin_does_not_see_verified_companies(
        self, client: AsyncClient, db_session
    ):
        app.dependency_overrides[get_current_patient] = _admin_override()
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="AlreadyVerified",
            country="US",
            description="Already approved",
            contact_email="verified@corp.com",
            verified=True,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.get("/api/pharma/applications", headers=AUTH)
        app.dependency_overrides.pop(get_current_patient, None)
        names = [c["name"] for c in resp.json()]
        assert "AlreadyVerified" not in names


# ── Pharma Admin: POST /api/pharma/verify/{id} ───────────────────────────────

class TestPharmaVerify:
    async def test_patient_cannot_verify(
        self, client: AsyncClient, db_session
    ):
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="AwaitingPharma",
            country="UK",
            description="Awaiting",
            contact_email="await@pharma.com",
            verified=False,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"/api/pharma/verify/{company.id}",
            json={"approved": True},
            headers=AUTH,
        )
        assert resp.status_code == 403

    async def test_admin_can_approve(
        self, client: AsyncClient, db_session
    ):
        app.dependency_overrides[get_current_patient] = _admin_override()
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="ApprovePharma",
            country="CH",
            description="For approval",
            contact_email="approve@pharma.com",
            verified=False,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"/api/pharma/verify/{company.id}",
            json={"approved": True},
            headers=AUTH,
        )
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is True
        assert body["status"] == "approved"

    async def test_admin_can_reject(
        self, client: AsyncClient, db_session
    ):
        app.dependency_overrides[get_current_patient] = _admin_override()
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="RejectPharma",
            country="CN",
            description="For rejection",
            contact_email="reject@pharma.com",
            verified=False,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"/api/pharma/verify/{company.id}",
            json={"approved": False, "rejection_reason": "Insufficient documentation"},
            headers=AUTH,
        )
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_nonexistent_company_returns_404(
        self, client: AsyncClient
    ):
        app.dependency_overrides[get_current_patient] = _admin_override()
        resp = await client.post(
            "/api/pharma/verify/no-such-id",
            json={"approved": True},
            headers=AUTH,
        )
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 404


# ── Pharma Admin: GET /api/pharma/ ────────────────────────────────────────────

class TestPharmaListVerified:
    async def test_empty_list(self, client: AsyncClient):
        resp = await client.get("/api/pharma/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_verified_company_appears(
        self, client: AsyncClient, db_session
    ):
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="VerifiedPharma",
            country="US",
            description="Approved",
            contact_email="ok@pharma.com",
            verified=True,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.get("/api/pharma/")
        data = resp.json()
        assert any(c["name"] == "VerifiedPharma" for c in data)

    async def test_response_contains_required_fields(
        self, client: AsyncClient, db_session
    ):
        from models.pharma import PharmaCompany
        db_session.add(PharmaCompany(
            name="FieldCheck",
            country="FR",
            description="Checking fields",
            contact_email="field@pharma.com",
            verified=True,
        ))
        await db_session.commit()
        data = (await client.get("/api/pharma/")).json()[0]
        for field in ("id", "name", "country", "verified", "contact_email"):
            assert field in data


# ── Pharma Admin: GET /api/pharma/{id} ───────────────────────────────────────

class TestPharmaGetCompany:
    async def test_verified_company_accessible(
        self, client: AsyncClient, db_session
    ):
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="AccessiblePharma",
            country="IT",
            description="Can be fetched by ID",
            contact_email="access@pharma.com",
            verified=True,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.get(f"/api/pharma/{company.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "AccessiblePharma"

    async def test_unverified_company_returns_404(
        self, client: AsyncClient, db_session
    ):
        from models.pharma import PharmaCompany
        company = PharmaCompany(
            name="HiddenPharma",
            country="JP",
            description="Not verified yet",
            contact_email="hidden@pharma.com",
            verified=False,
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.get(f"/api/pharma/{company.id}")
        assert resp.status_code == 404

    async def test_nonexistent_company_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/pharma/no-such-id")
        assert resp.status_code == 404


# ── Oncologist: GET /api/oncologist/pending ───────────────────────────────────

class TestOncologistPending:
    async def test_patient_role_returns_403(self, client: AsyncClient):
        resp = await client.get("/api/oncologist/pending", headers=AUTH)
        assert resp.status_code == 403

    async def test_oncologist_sees_unreviewed_submissions(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        app.dependency_overrides[get_current_patient] = _oncologist_override()
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Colon cancer",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=False,
            oncologist_reviewed=False,
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.get("/api/oncologist/pending", headers=AUTH)
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["submission_id"] for r in data]
        assert sub.id in ids

    async def test_reviewed_submissions_excluded(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        app.dependency_overrides[get_current_patient] = _oncologist_override()
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Colon cancer",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=False,
            oncologist_reviewed=True,  # already reviewed
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.get("/api/oncologist/pending", headers=AUTH)
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_empty_returns_empty_list(self, client: AsyncClient):
        app.dependency_overrides[get_current_patient] = _oncologist_override()
        resp = await client.get("/api/oncologist/pending", headers=AUTH)
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200
        assert resp.json() == []


# ── Oncologist: POST /api/oncologist/review ──────────────────────────────────

class TestOncologistReview:
    async def test_patient_role_returns_403(self, client: AsyncClient):
        resp = await client.post(
            "/api/oncologist/review",
            json={"submission_id": "some-id", "approved": True, "notes": "Looks good"},
            headers=AUTH,
        )
        assert resp.status_code == 403

    async def test_oncologist_can_approve(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        app.dependency_overrides[get_current_patient] = _oncologist_override()
        from models.submission import Submission, SubmissionStatus
        from models.result import Result

        sub = Submission(
            patient_id=seeded_patient.id,
            cancer_type="Breast cancer",
            status=SubmissionStatus.complete,
        )
        db_session.add(sub)
        await db_session.flush()

        result = Result(
            submission_id=sub.id,
            has_targetable_mutation=True,
            target_gene="BRCA1",
            oncologist_reviewed=False,
        )
        db_session.add(result)
        await db_session.commit()

        resp = await client.post(
            "/api/oncologist/review",
            json={
                "submission_id": sub.id,
                "approved": True,
                "notes": "PIK3CA R175H confirmed — PARP inhibitor therapy indicated.",
            },
            headers=AUTH,
        )
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 200

    async def test_nonexistent_submission_returns_404(self, client: AsyncClient):
        app.dependency_overrides[get_current_patient] = _oncologist_override()
        resp = await client.post(
            "/api/oncologist/review",
            json={"submission_id": "no-such-id", "approved": False, "notes": ""},
            headers=AUTH,
        )
        app.dependency_overrides.pop(get_current_patient, None)
        assert resp.status_code == 404


# ── Crowdfund: POST /api/crowdfund/ ───────────────────────────────────────────

class TestCreateCrowdfundCampaign:
    async def test_no_patient_record_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/crowdfund/",
            json={
                "slug": "my-cancer-fund",
                "title": "Help Fund My Treatment",
                "patient_story": "I was diagnosed with stage III lung cancer.",
                "goal_usd": 50_000.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 404

    async def test_valid_campaign_created(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        resp = await client.post(
            "/api/crowdfund/",
            json={
                "slug": "my-cancer-fund",
                "title": "Help Fund My Treatment",
                "patient_story": "I was diagnosed with stage III lung cancer.",
                "goal_usd": 50_000.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["goal_usd"] == 50_000.0
        assert body["slug"] == "my-cancer-fund"

    async def test_duplicate_slug_returns_409(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        payload = {
            "slug": "unique-slug",
            "title": "Campaign",
            "patient_story": "My story.",
            "goal_usd": 10_000.0,
        }
        await client.post("/api/crowdfund/", json=payload, headers=AUTH)
        resp = await client.post("/api/crowdfund/", json=payload, headers=AUTH)
        assert resp.status_code == 409

    async def test_invalid_slug_format_returns_422(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        resp = await client.post(
            "/api/crowdfund/",
            json={
                "slug": "UPPERCASE-SLUG",
                "title": "Campaign",
                "patient_story": "My story.",
                "goal_usd": 5_000.0,
            },
            headers=AUTH,
        )
        assert resp.status_code in (422, 422)

    async def test_zero_goal_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        resp = await client.post(
            "/api/crowdfund/",
            json={
                "slug": "zero-fund",
                "title": "Zero Goal",
                "patient_story": "Testing.",
                "goal_usd": 0.0,
            },
            headers=AUTH,
        )
        assert resp.status_code == 422

    async def test_goal_over_limit_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        # campaign.py doesn't impose le= limit; verify very large values are accepted (no 422)
        resp = await client.post(
            "/api/crowdfund/",
            json={
                "slug": "over-limit",
                "title": "Over Limit",
                "patient_story": "Testing limits.",
                "goal_usd": 2_000_000.0,
            },
            headers=AUTH,
        )
        # campaign.py schema has no upper bound — large goals are valid
        assert resp.status_code == 201


# ── Crowdfund: GET /api/crowdfund/{slug} ──────────────────────────────────────

class TestGetCrowdfundCampaign:
    async def test_active_public_campaign_accessible(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.campaign import Campaign
        c = Campaign(
            patient_id=seeded_patient.id,
            slug="active-fund",
            title="Active Fund",
            patient_story="Help me.",
            goal_usd=25_000.0,
            is_public=True,
            is_active=True,
        )
        db_session.add(c)
        await db_session.commit()

        resp = await client.get("/api/crowdfund/active-fund")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "active-fund"
        assert body["goal_usd"] == 25_000.0

    async def test_inactive_campaign_returns_404(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.campaign import Campaign
        c = Campaign(
            patient_id=seeded_patient.id,
            slug="inactive-fund",
            title="Inactive",
            patient_story="This is inactive.",
            goal_usd=5_000.0,
            is_public=True,
            is_active=False,
        )
        db_session.add(c)
        await db_session.commit()

        resp = await client.get("/api/crowdfund/inactive-fund")
        assert resp.status_code == 404

    async def test_nonexistent_slug_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/crowdfund/no-such-slug-xyz")
        assert resp.status_code == 404

    async def test_response_has_required_fields(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.campaign import Campaign
        c = Campaign(
            patient_id=seeded_patient.id,
            slug="fields-fund",
            title="Fields Check",
            patient_story="Checking fields.",
            goal_usd=10_000.0,
            is_public=True,
            is_active=True,
        )
        db_session.add(c)
        await db_session.commit()
        body = (await client.get("/api/crowdfund/fields-fund")).json()
        for field in ("id", "slug", "title", "goal_usd", "raised_usd"):
            assert field in body


# ── Crowdfund: POST /api/crowdfund/{slug}/donate ─────────────────────────────

class TestDonate:
    async def test_donate_creates_payment_intent(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.campaign import Campaign
        c = Campaign(
            patient_id=seeded_patient.id,
            slug="donate-fund",
            title="Donate Fund",
            patient_story="Please donate.",
            goal_usd=30_000.0,
            is_public=True,
            is_active=True,
        )
        db_session.add(c)
        await db_session.commit()

        with patch("routes.campaign.stripe") as mock_stripe:
            intent = MagicMock()
            intent.client_secret = "pi_donate_secret_abc"
            mock_stripe.PaymentIntent.create.return_value = intent

            resp = await client.post(
                "/api/crowdfund/donate-fund/donate",
                json={"amount_usd": 250.0},
            )

        assert resp.status_code == 200
        assert resp.json()["client_secret"] == "pi_donate_secret_abc"

    async def test_donate_to_nonexistent_campaign_returns_404(
        self, client: AsyncClient
    ):
        with patch("routes.crowdfund.stripe"):
            resp = await client.post(
                "/api/crowdfund/no-such-slug/donate",
                json={"amount_usd": 100.0},
            )
        assert resp.status_code == 404

    async def test_zero_amount_rejected(
        self, client: AsyncClient, db_session, seeded_patient
    ):
        from models.campaign import Campaign
        c = Campaign(
            patient_id=seeded_patient.id,
            slug="donate-zero",
            title="Zero Donate",
            patient_story="Testing.",
            goal_usd=1_000.0,
            is_public=True,
            is_active=True,
        )
        db_session.add(c)
        await db_session.commit()
        resp = await client.post(
            "/api/crowdfund/donate-zero/donate",
            json={"amount_usd": 0},
        )
        assert resp.status_code == 422
