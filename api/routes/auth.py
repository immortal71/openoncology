"""
Auth route — JWT token introspection via Keycloak.

Patients authenticate directly through Keycloak (OIDC).
The API validates the Bearer token on every protected request.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx

from config import settings
from middleware.rate_limit import limiter, AUTH_LIMIT

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer()


async def _get_keycloak_public_key() -> str:
    """Fetch Keycloak realm's RSA public key for JWT verification."""
    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        # Keycloak returns the key as a raw base64 string
        raw_key = data["public_key"]
        return f"-----BEGIN PUBLIC KEY-----\n{raw_key}\n-----END PUBLIC KEY-----"


async def get_current_patient(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Dependency — validates the Keycloak JWT and returns the token payload.
    Raises 401 if the token is invalid or expired.
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
        public_key = await _get_keycloak_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="account",
            options={"verify_aud": False},
        )
        return payload
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


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
