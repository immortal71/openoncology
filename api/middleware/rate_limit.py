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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Initialise with Redis as the storage backend when available, else in-memory
def _make_limiter() -> Limiter:
    try:
        from config import settings
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
