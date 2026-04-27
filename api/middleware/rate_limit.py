"""
Rate Limiting Middleware using SlowAPI (limits.storage backed by Redis).

Protects against OWASP A07 (Identification & Authentication Failures) and
brute-force / enumeration attacks.

Default limits:
  - Auth endpoints      : 10 req / minute  (strict)
  - Submission upload   : 5  req / minute  (VCF uploads are expensive)
  - Genomic API (read)  : 60 req / minute  (normal: browsing results)
  - Global default      : 120 req / minute per IP

Limits are per-IP (X-Forwarded-For trusted via nginx ingress).
"""
import socket
from urllib.parse import urlparse

from slowapi import Limiter
from slowapi.util import get_remote_address


def _redis_reachable(redis_url: str) -> bool:
    parsed = urlparse(redis_url)
    host = parsed.hostname
    port = parsed.port or 6379
    if not host:
        return False

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


# Initialise with Redis as the storage backend when available, else in-memory
def _make_limiter() -> Limiter:
    try:
        from config import settings
        if settings.environment == "development" and not _redis_reachable(settings.redis_url):
            return Limiter(
                key_func=get_remote_address,
                default_limits=["120/minute"],
            )
        return Limiter(
            key_func=get_remote_address,
            storage_uri=settings.redis_url,
            default_limits=["120/minute"],
        )
    except Exception:
        return Limiter(
            key_func=get_remote_address,
            default_limits=["120/minute"],
        )


limiter = _make_limiter()

# Per-route limit decorators — import and use in route files:
#   from middleware.rate_limit import limiter
#   @router.post("/login")
#   @limiter.limit("10/minute")
#   async def login(request: Request, ...): ...

AUTH_LIMIT = "10/minute"
UPLOAD_LIMIT = "5/minute"
READ_LIMIT = "60/minute"
