"""Two Stripe-facing defects: a replayed webhook, and an open oracle.

Neither endpoint had any test at all. Between them they are the only path in the
system that moves money and one of the few that answers questions without a
credential.

`POST /api/webhook/stripe` incremented `campaign.raised_usd` once per delivery.
Stripe documents at-least-once delivery and redelivers on any non-2xx or
timeout, so the total drifted upward under entirely normal operation, and an
inflated campaign figure looks the same as a successful campaign.

`GET /api/stripe/connect/return/{pharma_id}` is the Stripe `return_url` and so
cannot require a bearer token, but it returned `stripe_account_id`,
`charges_enabled` and `payouts_enabled` for any id in the path.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from models.campaign import Campaign  # noqa: E402
from models.pharma import PharmaCompany  # noqa: E402


def _event(event_id: str, campaign_id: str, amount_cents: int = 5000) -> dict:
    return {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_" + event_id,
                "amount_received": amount_cents,
                "metadata": {"type": "donation", "campaign_id": campaign_id},
            }
        },
    }


@pytest.fixture()
def accept_any_signature(monkeypatch):
    """Bypass signature verification; these tests are about what happens after."""
    def _construct(payload, _sig, _secret):
        return json.loads(payload)

    monkeypatch.setattr("stripe.Webhook.construct_event", _construct)


@pytest.fixture()
async def campaign(db_session, seeded_patient):
    row = Campaign(
        patient_id=seeded_patient.id,
        title="Test campaign",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        goal_usd=1000.0,
        raised_usd=0.0,
    )
    db_session.add(row)
    await db_session.commit()
    return row


class TestWebhookReplay:
    async def test_one_delivery_credits_once(
        self, client, campaign, db_session, accept_any_signature
    ):
        payload = _event("evt_single", campaign.id, 5000)
        response = await client.post(
            "/api/webhook/stripe", json=payload, headers={"stripe-signature": "x"}
        )
        assert response.status_code == 200

        await db_session.refresh(campaign)
        assert campaign.raised_usd == pytest.approx(50.0)

    async def test_a_redelivered_event_does_not_credit_again(
        self, client, campaign, db_session, accept_any_signature
    ):
        """The defect. Stripe sends the same event id again; the total must hold."""
        payload = _event("evt_replay", campaign.id, 5000)
        headers = {"stripe-signature": "x"}

        first = await client.post("/api/webhook/stripe", json=payload, headers=headers)
        second = await client.post("/api/webhook/stripe", json=payload, headers=headers)
        third = await client.post("/api/webhook/stripe", json=payload, headers=headers)

        assert first.status_code == second.status_code == third.status_code == 200
        assert second.json().get("duplicate") is True
        assert third.json().get("duplicate") is True

        await db_session.refresh(campaign)
        assert campaign.raised_usd == pytest.approx(50.0), (
            "a redelivered event credited the campaign again; Stripe retries on "
            "any non-2xx or timeout, so this inflates the total in normal operation"
        )

    async def test_distinct_events_both_credit(
        self, client, campaign, db_session, accept_any_signature
    ):
        """Idempotency must key on the event id, not on the amount or campaign."""
        headers = {"stripe-signature": "x"}
        await client.post(
            "/api/webhook/stripe", json=_event("evt_a", campaign.id, 5000), headers=headers
        )
        await client.post(
            "/api/webhook/stripe", json=_event("evt_b", campaign.id, 2500), headers=headers
        )

        await db_session.refresh(campaign)
        assert campaign.raised_usd == pytest.approx(75.0)

    async def test_a_replay_is_still_acknowledged(
        self, client, campaign, accept_any_signature
    ):
        """A duplicate must return 2xx, or Stripe keeps retrying it forever."""
        payload = _event("evt_ack", campaign.id)
        headers = {"stripe-signature": "x"}
        await client.post("/api/webhook/stripe", json=payload, headers=headers)
        again = await client.post("/api/webhook/stripe", json=payload, headers=headers)

        assert again.status_code == 200
        assert again.json()["received"] is True


class TestOnboardingReturnDisclosesNothing:
    @pytest.fixture()
    async def company(self, db_session):
        row = PharmaCompany(
            name="Acme Pharma",
            country="DE",
            contact_email="ops@acme.test",
            stripe_account_id="acct_SECRET123",
        )
        db_session.add(row)
        await db_session.commit()
        return row

    @pytest.fixture()
    def stripe_account(self, monkeypatch):
        monkeypatch.setattr(
            "stripe.Account.retrieve",
            lambda _id: {
                "id": "acct_SECRET123",
                "details_submitted": True,
                "charges_enabled": True,
                "payouts_enabled": True,
            },
        )

    async def test_it_stays_reachable_without_a_token(
        self, client, company, stripe_account
    ):
        """It is Stripe's return_url, so requiring auth would break onboarding."""
        response = await client.get(f"/api/stripe/connect/return/{company.id}")
        assert response.status_code == 200

    async def test_the_stripe_account_id_is_not_disclosed(
        self, client, company, stripe_account
    ):
        response = await client.get(f"/api/stripe/connect/return/{company.id}")
        body = response.text
        assert "acct_SECRET123" not in body
        assert "stripe_account_id" not in response.json()

    async def test_capability_flags_are_not_disclosed(
        self, client, company, stripe_account
    ):
        payload = response_json = (
            await client.get(f"/api/stripe/connect/return/{company.id}")
        ).json()
        assert "charges_enabled" not in payload
        assert "payouts_enabled" not in response_json

    async def test_an_unknown_id_is_indistinguishable_from_a_known_one(
        self, client, company, stripe_account
    ):
        """Differing status or shape would confirm which pharma ids exist."""
        known = await client.get(f"/api/stripe/connect/return/{company.id}")
        unknown = await client.get(f"/api/stripe/connect/return/{uuid.uuid4()}")

        assert known.status_code == unknown.status_code == 200
        assert set(known.json()) == set(unknown.json())

    async def test_the_detail_endpoint_still_requires_admin(self, client, company):
        """What was removed here is available from /status, behind the admin role."""
        response = await client.get(f"/api/stripe/connect/status/{company.id}")
        assert response.status_code == 403
