"""
HIPAA Audit Logging Middleware.

Logs every request that touches Protected Health Information (PHI) to a
structured audit log.  Required by HIPAA Security Rule §164.312(b).

Logged fields (never log PHI values — only metadata):
  - timestamp (UTC ISO-8601)
  - request_id (UUID per request)
  - user_id  (Keycloak subject claim, or "anonymous")
  - method, path, status_code
  - ip_address (X-Forwarded-For or client host)
  - user_agent
  - duration_ms
"""
import json
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Routes that handle PHI — all others are ignored
_PHI_PREFIXES = (
    "/api/submit",
    "/api/results",
    "/api/repurposing",
    "/api/oncologist",
    "/api/me",
    "/api/crowdfund",
    "/api/pharma",
    "/api/marketplace",
    "/api/stripe",
)

audit_logger = logging.getLogger("openoncology.audit")


class AuditMiddleware(BaseHTTPMiddleware):
    """Structured HIPAA audit log for all PHI-touching endpoints."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Fast-path: skip non-PHI routes (health, docs, static assets)
        if not any(request.url.path.startswith(p) for p in _PHI_PREFIXES):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # Extract user from token without full validation (audit only)
        user_id = _extract_user_id(request)

        # Attach request_id to scope so route handlers can reference it
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        ip = _client_ip(request)

        audit_logger.info(
            json.dumps(
                {
                    "event": "phi_access",
                    "request_id": request_id,
                    "timestamp": _utc_now(),
                    "user_id": user_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "ip": ip,
                    "user_agent": request.headers.get("user-agent", ""),
                    "duration_ms": duration_ms,
                },
                separators=(",", ":"),
            )
        )

        # Expose request-id to client for support tracing
        response.headers["X-Request-Id"] = request_id
        return response


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_user_id(request: Request) -> str:
    """Decode sub claim from Bearer JWT without verifying signature (audit only)."""
    try:
        import base64

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return "anonymous"
        token = auth.split(" ", 1)[1]
        payload_b64 = token.split(".")[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        payload_b64 += "=" * (padding % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub", "unknown")
    except Exception:
        return "unknown"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Only trust the first IP in the chain
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _utc_now() -> str:
    from datetime import datetime, UTC
    return datetime.now(UTC).isoformat()
