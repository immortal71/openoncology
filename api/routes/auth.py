"""
Auth route — JWT verification against Keycloak's JWKS.

Patients authenticate directly through Keycloak (OIDC).
The API validates the Bearer token on every protected request.

Verification reads the realm's JWKS rather than the legacy `public_key` field
on the realm endpoint, and the key set is cached. Three reasons, in the order
they bite:

  * The legacy field carries one key. Keycloak rotates realm keys, and during a
    rotation it signs with the new key while the old one is still valid. A
    verifier that knows a single key rejects every token minted after the
    rotation until it happens to refetch. JWKS publishes the whole set, keyed by
    `kid`, so both are present.
  * The fetch ran on every authenticated request. `get_current_patient` guards
    45 route dependencies, so each protected call made a second outbound HTTP
    round trip before it could do any work, and Keycloak being slow or down took
    the whole API with it. The set now lives in a process-local cache with a
    TTL, refreshed on a `kid` miss so a rotation is picked up without waiting for
    the TTL to lapse.
  * `audience` was passed and then disabled with `verify_aud: False`, which
    reads like a check and is not one. Any token from any client in the realm
    verified here. Audience is enforced whenever `KEYCLOAK_AUDIENCE` is set, and
    `config.py` requires it to be set in production.
"""
import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx

from config import settings
from middleware.rate_limit import limiter, AUTH_LIMIT

logger = logging.getLogger("openoncology.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer()

# Only RS256 is accepted. Reading the algorithm out of the token's own header is
# how alg-confusion attacks start, so the list is fixed here rather than derived
# from the JWK.
_ALLOWED_ALGORITHMS = ["RS256"]

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock = asyncio.Lock()


def _issuer() -> str:
    """
    The `iss` value tokens are expected to carry.

    Configurable rather than always derived, because inside a cluster
    `keycloak_url` is usually the internal Service address while Keycloak keeps
    signing with its public hostname. Deriving `iss` from the internal URL
    rejects every valid token in exactly that deployment.
    """
    configured = (settings.keycloak_issuer or "").strip().rstrip("/")
    if configured:
        return configured
    return f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"


def _jwks_url() -> str:
    """JWKS is fetched over the internal URL even when `iss` is the public one."""
    base = settings.keycloak_url.rstrip("/")
    return f"{base}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"


def _reset_jwks_cache() -> None:
    """Drop the cached key set. Used by tests and after a realm reconfiguration."""
    global _jwks_cache, _jwks_fetched_at
    _jwks_cache = None
    _jwks_fetched_at = 0.0


async def _fetch_jwks() -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(_jwks_url(), timeout=settings.keycloak_jwks_timeout_seconds)
        resp.raise_for_status()
        return resp.json()


async def _get_jwks(force_refresh: bool = False) -> dict:
    """
    Return the realm's key set, from cache when it is still fresh.

    A stale cache beats a failed fetch: if Keycloak is unreachable but the last
    known key set is still in hand, tokens signed by those keys keep verifying.
    That is the difference between the identity provider being down and the
    entire API being down with it.
    """
    global _jwks_cache, _jwks_fetched_at

    age = time.monotonic() - _jwks_fetched_at
    fresh = _jwks_cache is not None and age < settings.keycloak_jwks_cache_seconds
    if fresh and not force_refresh:
        return _jwks_cache

    async with _jwks_lock:
        age = time.monotonic() - _jwks_fetched_at
        fresh = _jwks_cache is not None and age < settings.keycloak_jwks_cache_seconds
        if fresh and not force_refresh:
            return _jwks_cache

        try:
            jwks = await _fetch_jwks()
        except httpx.HTTPError as exc:
            if _jwks_cache is not None:
                logger.warning(
                    "auth.jwks_refresh_failed_serving_stale",
                    extra={"error": str(exc), "age_seconds": round(age, 1)},
                )
                return _jwks_cache
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc

        _jwks_cache = jwks
        _jwks_fetched_at = time.monotonic()
        return jwks


def _select_key(jwks: dict, kid: str | None) -> dict | None:
    keys = [
        k for k in (jwks or {}).get("keys", [])
        if k.get("alg", "RS256") in _ALLOWED_ALGORITHMS
    ]
    if not keys:
        return None
    if kid is None:
        # A token with no `kid` is only unambiguous when the realm publishes one
        # usable key. Guessing among several is how the wrong key gets trusted.
        return keys[0] if len(keys) == 1 else None
    for key in keys:
        if key.get("kid") == kid:
            return key
    return None


def _decode_options() -> dict:
    return {
        "verify_signature": True,
        "verify_aud": bool((settings.keycloak_audience or "").strip()),
        "verify_iss": True,
        "verify_exp": True,
        "verify_nbf": True,
        "require_exp": True,
    }


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_patient(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Dependency — validates the Keycloak JWT and returns the token payload.
    Raises 401 if the token is invalid, expired, or issued for another audience.
    """
    token = credentials.credentials
    if settings.environment == "development" and token == "demo-local-token":
        return {
            "sub": "demo-user",
            "email": "demo@openoncology.local",
            "name": "Local Demo User",
            "realm_access": {"roles": ["patient"]},
        }

    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except JWTError as exc:
        raise _unauthorized() from exc

    key = _select_key(await _get_jwks(), kid)
    if key is None:
        # An unknown `kid` is the normal signature of a key rotation, so refetch
        # once before deciding the token is bad.
        key = _select_key(await _get_jwks(force_refresh=True), kid)

    if key is None:
        logger.warning("auth.no_matching_signing_key", extra={"kid": kid})
        raise _unauthorized()

    try:
        return jwt.decode(
            token,
            key,
            algorithms=_ALLOWED_ALGORITHMS,
            issuer=_issuer(),
            audience=(settings.keycloak_audience or "").strip() or None,
            options=_decode_options(),
        )
    except JWTError as exc:
        raise _unauthorized() from exc


@router.get("/me")
@limiter.limit(AUTH_LIMIT)
async def get_me(request: Request, patient: dict = Depends(get_current_patient)):
    """Return the authenticated patient's token claims."""
    return {
        "id": patient.get("sub"),
        "email": patient.get("email"),
        "name": patient.get("name"),
        "roles": patient.get("realm_access", {}).get("roles", []),
    }
