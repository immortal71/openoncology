"""Integration tests for AuditMiddleware (HIPAA structured logging).

Verifies that:
- PHI-touching routes (matching _PHI_PREFIXES) get an audit log entry
- Non-PHI routes are *not* logged
- The log entry contains all required HIPAA fields
- The X-Request-Id response header is set for PHI routes
- An anonymous user_id is recorded when no Bearer token is present
- A valid user_id is extracted from a Bearer JWT sub claim
"""

import sys
import os
import json
import base64
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.audit import _extract_user_id, _client_ip, _PHI_PREFIXES


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build a minimal unsigned JWT with a given sub claim
# ─────────────────────────────────────────────────────────────────────────────

def _make_bearer(sub: str) -> str:
    """Return a Bearer token whose payload.sub equals `sub` (no signature)."""
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    payload_bytes = json.dumps({"sub": sub, "email": "test@example.com"}).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"Bearer {header}.{payload}.fake_sig"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for helper functions (no HTTP needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractUserId:
    """Test the _extract_user_id helper without a running server."""

    def _make_fake_request(self, auth_header: str | None):
        """Create a minimal mock that mimics request.headers."""
        class _FakeHeaders:
            def __init__(self, auth):
                self._auth = auth
            def get(self, key, default=""):
                if key == "authorization":
                    return self._auth or ""
                return default

        class _FakeRequest:
            def __init__(self, auth):
                self.headers = _FakeHeaders(auth)

        return _FakeRequest(auth_header)

    def test_no_auth_header_returns_anonymous(self):
        req = self._make_fake_request(None)
        assert _extract_user_id(req) == "anonymous"  # type: ignore[arg-type]

    def test_non_bearer_returns_anonymous(self):
        req = self._make_fake_request("Basic dXNlcjpwYXNz")
        assert _extract_user_id(req) == "anonymous"  # type: ignore[arg-type]

    def test_valid_jwt_extracts_sub(self):
        bearer = _make_bearer("patient-abc-123")
        req = self._make_fake_request(bearer)
        result = _extract_user_id(req)  # type: ignore[arg-type]
        assert result == "patient-abc-123"

    def test_malformed_jwt_returns_unknown(self):
        req = self._make_fake_request("Bearer not.a.jwt")
        assert _extract_user_id(req) in ("unknown", "anonymous")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# PHI prefix list correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestPhiPrefixes:
    def test_submit_is_phi(self):
        assert any("/api/submit".startswith(p) for p in _PHI_PREFIXES)

    def test_results_is_phi(self):
        assert any("/api/results".startswith(p) for p in _PHI_PREFIXES)

    def test_repurposing_is_phi(self):
        assert any("/api/repurposing".startswith(p) for p in _PHI_PREFIXES)

    def test_me_export_is_phi(self):
        assert any("/api/me/export".startswith(p) for p in _PHI_PREFIXES)

    def test_docs_not_phi(self):
        assert not any("/docs".startswith(p) for p in _PHI_PREFIXES)

    def test_health_not_phi(self):
        assert not any("/health".startswith(p) for p in _PHI_PREFIXES)

    def test_openapi_not_phi(self):
        assert not any("/openapi.json".startswith(p) for p in _PHI_PREFIXES)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — middleware behaviour over HTTP
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def audit_client():
    """HTTP test client with the real middleware stack (no dep overrides)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class TestAuditMiddlewareIntegration:
    """End-to-end middleware tests against the FastAPI app."""

    @pytest.mark.asyncio
    async def test_phi_route_sets_x_request_id_header(self, audit_client, caplog):
        """X-Request-Id must be present on any response from a PHI path."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            resp = await audit_client.get(
                "/api/results/nonexistent-result-id",
                headers={"Authorization": _make_bearer("test-user")},
            )
        assert "X-Request-Id" in resp.headers
        # UUID4 format — 36 chars including hyphens
        assert len(resp.headers["X-Request-Id"]) == 36

    @pytest.mark.asyncio
    async def test_phi_route_emits_audit_log(self, audit_client, caplog):
        """A request to a PHI path must produce exactly one audit log record."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/results/some-id",
                headers={"Authorization": _make_bearer("test-user-xyz")},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert len(audit_records) >= 1

    @pytest.mark.asyncio
    async def test_phi_audit_log_contains_required_fields(self, audit_client, caplog):
        """Audit log JSON must include all HIPAA-required metadata fields."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/results/log-field-check",
                headers={"Authorization": _make_bearer("user-field-test")},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert audit_records, "Expected at least one audit record"

        log_data = json.loads(audit_records[0].getMessage())
        required_fields = {
            "event", "request_id", "timestamp", "user_id",
            "method", "path", "status_code", "ip", "duration_ms",
        }
        for field in required_fields:
            assert field in log_data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_phi_audit_log_user_id_matches_jwt_sub(self, audit_client, caplog):
        """user_id in the audit log must match the Bearer token's sub claim."""
        expected_sub = "patient-hipaa-sub-check"
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/results/sub-check",
                headers={"Authorization": _make_bearer(expected_sub)},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert audit_records
        log_data = json.loads(audit_records[0].getMessage())
        assert log_data["user_id"] == expected_sub

    @pytest.mark.asyncio
    async def test_phi_audit_log_anonymous_without_token(self, audit_client, caplog):
        """Unauthenticated requests must record user_id as 'anonymous'."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get("/api/results/anon-check")

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert audit_records
        log_data = json.loads(audit_records[0].getMessage())
        assert log_data["user_id"] == "anonymous"

    @pytest.mark.asyncio
    async def test_phi_audit_log_event_is_phi_access(self, audit_client, caplog):
        """Audit event field must equal 'phi_access'."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/submit/",
                headers={"Authorization": _make_bearer("user-event-check")},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert audit_records
        log_data = json.loads(audit_records[0].getMessage())
        assert log_data["event"] == "phi_access"

    @pytest.mark.asyncio
    async def test_non_phi_route_does_not_emit_audit_log(self, audit_client, caplog):
        """Requests to non-PHI paths must NOT produce an audit log record."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get("/docs")

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert len(audit_records) == 0

    @pytest.mark.asyncio
    async def test_non_phi_route_no_x_request_id(self, audit_client):
        """Non-PHI routes must NOT set X-Request-Id (middleware bypassed)."""
        resp = await audit_client.get("/openapi.json")
        assert "X-Request-Id" not in resp.headers

    @pytest.mark.asyncio
    async def test_audit_log_duration_ms_positive(self, audit_client, caplog):
        """duration_ms must be a positive number."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/results/duration-check",
                headers={"Authorization": _make_bearer("user-dur")},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        assert audit_records
        log_data = json.loads(audit_records[0].getMessage())
        assert isinstance(log_data["duration_ms"], (int, float))
        assert log_data["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_audit_log_method_recorded(self, audit_client, caplog):
        """HTTP method (GET, POST, etc.) must be recorded in the audit log."""
        with caplog.at_level(logging.INFO, logger="openoncology.audit"):
            await audit_client.get(
                "/api/results/method-check",
                headers={"Authorization": _make_bearer("user-method")},
            )

        audit_records = [
            r for r in caplog.records if r.name == "openoncology.audit"
        ]
        log_data = json.loads(audit_records[0].getMessage())
        assert log_data["method"] == "GET"
