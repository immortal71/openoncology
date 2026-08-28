"""
Verification tests for the Keycloak JWT path.

Every one of these fails against the previous implementation, which fetched the
realm's single legacy public key on each request and then disabled the audience
check it appeared to perform. They are grouped by the property being asserted
rather than by function, because the properties are what the 45 routes behind
`get_current_patient` actually depend on.

Tokens are minted here with a locally generated RSA key, so nothing reaches the
network: the JWKS fetch is stubbed and asserted on directly.
"""
import time

import httpx
import pytest
from jose import jwt
from jose.constants import ALGORITHMS
from jose.utils import long_to_base64

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from routes import auth


ISSUER = "https://id.example.org/realms/openoncology"
AUDIENCE = "openoncology-api"

# Keys are generated once per seed and reused. python-jose runs on whichever
# backend is installed, and on the pure-Python `rsa` one a 2048-bit keygen costs
# about three seconds, which is worth paying four times rather than twenty.
_KEY_CACHE: dict[str, tuple[str, int, int]] = {}


def _generate_rsa() -> tuple[str, int, int]:
    """Return (private_pem, n, e) using whichever RSA backend is available."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa as c_rsa

        private = c_rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        numbers = private.public_key().public_numbers()
        return pem, numbers.n, numbers.e
    except ImportError:
        import rsa as pure_rsa

        public, private = pure_rsa.newkeys(2048)
        return private.save_pkcs1("PEM").decode(), public.n, public.e


def _keypair(kid: str, seed: str | None = None):
    """
    Return (private_pem, jwk_dict) for an RSA key published under `kid`.

    `seed` names the underlying key material, so two callers can publish
    different keys under the same `kid` — which is what a forged token looks
    like, and one of the cases below.
    """
    seed = seed or kid
    if seed not in _KEY_CACHE:
        _KEY_CACHE[seed] = _generate_rsa()
    pem, n, e = _KEY_CACHE[seed]
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "alg": "RS256",
        "use": "sig",
        "n": long_to_base64(n).decode(),
        "e": long_to_base64(e).decode(),
    }
    return pem, jwk


def _token(pem: str, kid: str, **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": "patient-1",
        "email": "patient@example.org",
        "name": "Test Patient",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "realm_access": {"roles": ["patient"]},
    }
    claims.update(overrides)
    return jwt.encode(claims, pem, algorithm=ALGORITHMS.RS256, headers={"kid": kid})


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def realm(monkeypatch):
    """
    A realm with one signing key, a stubbed JWKS endpoint, and a fetch counter.

    `fetches` is the thing several tests are really about: the old code made one
    outbound request per authenticated call.
    """
    pem, jwk = _keypair("key-1")
    state = {"keys": [jwk], "fetches": 0, "fail": False}

    async def _fake_fetch():
        state["fetches"] += 1
        if state["fail"]:
            raise httpx.ConnectError("keycloak unreachable")
        return {"keys": list(state["keys"])}

    monkeypatch.setattr(auth, "_fetch_jwks", _fake_fetch)
    monkeypatch.setattr("config.settings.environment", "production", raising=False)
    monkeypatch.setattr("config.settings.keycloak_issuer", ISSUER, raising=False)
    monkeypatch.setattr("config.settings.keycloak_audience", AUDIENCE, raising=False)
    monkeypatch.setattr("config.settings.keycloak_jwks_cache_seconds", 300, raising=False)
    auth._reset_jwks_cache()
    yield {"pem": pem, "jwk": jwk, "state": state}
    auth._reset_jwks_cache()


# ── The key set is cached ────────────────────────────────────────────────────

async def test_valid_token_is_accepted(realm):
    payload = await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert payload["sub"] == "patient-1"
    assert payload["aud"] == AUDIENCE


async def test_repeated_requests_fetch_the_key_set_once(realm):
    for _ in range(10):
        await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert realm["state"]["fetches"] == 1


async def test_expired_cache_refetches(realm, monkeypatch):
    await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    monkeypatch.setattr("config.settings.keycloak_jwks_cache_seconds", 0, raising=False)
    await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert realm["state"]["fetches"] == 2


async def test_stale_key_set_is_served_when_keycloak_is_down(realm, monkeypatch):
    """
    Keycloak being unreachable must not take the API down with it. The last known
    key set still verifies tokens signed by those keys.
    """
    await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    monkeypatch.setattr("config.settings.keycloak_jwks_cache_seconds", 0, raising=False)
    realm["state"]["fail"] = True

    payload = await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert payload["sub"] == "patient-1"


async def test_unreachable_keycloak_with_no_cache_is_503(realm):
    realm["state"]["fail"] = True
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert exc.value.status_code == 503


# ── Key rotation ─────────────────────────────────────────────────────────────

async def test_rotated_key_is_picked_up_without_waiting_for_the_ttl(realm):
    """
    A realm rotation mints tokens under a `kid` the cache has never seen. One
    forced refresh resolves it; the legacy single-key path could not.
    """
    await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    new_pem, new_jwk = _keypair("key-2")
    realm["state"]["keys"] = [realm["jwk"], new_jwk]

    payload = await auth.get_current_patient(_credentials(_token(new_pem, "key-2")))
    assert payload["sub"] == "patient-1"
    assert realm["state"]["fetches"] == 2


async def test_unknown_kid_refreshes_only_once_before_rejecting(realm):
    stranger_pem, _ = _keypair("attacker-key")
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(_token(stranger_pem, "attacker-key")))
    assert exc.value.status_code == 401
    assert realm["state"]["fetches"] == 2


# ── Claims that are actually verified ────────────────────────────────────────

async def test_token_for_another_client_in_the_realm_is_rejected(realm):
    """
    The finding this file exists for. The realm signs tokens for every client it
    hosts; only the ones minted for this API may authenticate against it.
    """
    token = _token(realm["pem"], "key-1", aud="some-other-client")
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(token))
    assert exc.value.status_code == 401


async def test_token_from_another_issuer_is_rejected(realm):
    token = _token(realm["pem"], "key-1", iss="https://evil.example.org/realms/openoncology")
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(token))
    assert exc.value.status_code == 401


async def test_expired_token_is_rejected(realm):
    past = int(time.time()) - 3600
    token = _token(realm["pem"], "key-1", iat=past, exp=past + 60)
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(token))
    assert exc.value.status_code == 401


async def test_token_signed_by_an_unrelated_key_is_rejected(realm):
    """Same `kid` as the realm's key, different private key behind it."""
    stranger_pem, _ = _keypair("key-1", seed="stranger")
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(_token(stranger_pem, "key-1")))
    assert exc.value.status_code == 401


async def test_malformed_token_is_rejected(realm):
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials("not-a-jwt"))
    assert exc.value.status_code == 401


# ── Algorithm handling ───────────────────────────────────────────────────────

async def test_symmetric_algorithm_is_not_accepted(realm):
    """
    Alg confusion: a token signed HS256 using the realm's public modulus as the
    shared secret. Accepting the algorithm named in the token's own header is
    what makes that work, so the accepted list is fixed in code.
    """
    now = int(time.time())
    forged = jwt.encode(
        {"sub": "patient-1", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300},
        realm["jwk"]["n"],
        algorithm=ALGORITHMS.HS256,
        headers={"kid": "key-1"},
    )
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(forged))
    assert exc.value.status_code == 401


async def test_key_set_with_no_usable_key_is_rejected(realm):
    realm["state"]["keys"] = [{"kty": "oct", "kid": "key-1", "alg": "HS256"}]
    auth._reset_jwks_cache()
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(_token(realm["pem"], "key-1")))
    assert exc.value.status_code == 401


async def test_kidless_token_is_ambiguous_when_the_realm_publishes_two_keys(realm):
    _, second = _keypair("key-2")
    realm["state"]["keys"] = [realm["jwk"], second]
    auth._reset_jwks_cache()

    now = int(time.time())
    token = jwt.encode(
        {"sub": "patient-1", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300},
        realm["pem"],
        algorithm=ALGORITHMS.RS256,
    )
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials(token))
    assert exc.value.status_code == 401


# ── Issuer and audience configuration ────────────────────────────────────────

async def test_issuer_defaults_to_the_realm_url_when_not_configured(monkeypatch):
    monkeypatch.setattr("config.settings.keycloak_issuer", "", raising=False)
    monkeypatch.setattr("config.settings.keycloak_url", "http://keycloak:8080/", raising=False)
    monkeypatch.setattr("config.settings.keycloak_realm", "openoncology", raising=False)
    assert auth._issuer() == "http://keycloak:8080/realms/openoncology"


async def test_configured_issuer_overrides_the_derived_one(monkeypatch):
    """
    The internal/external split: the API dials the cluster Service, tokens carry
    the public hostname. Deriving `iss` from the dial address rejects every
    valid token in that deployment.
    """
    monkeypatch.setattr("config.settings.keycloak_url", "http://keycloak:8080", raising=False)
    monkeypatch.setattr("config.settings.keycloak_issuer", ISSUER, raising=False)
    assert auth._issuer() == ISSUER
    assert auth._jwks_url().startswith("http://keycloak:8080/")


async def test_audience_check_is_skipped_when_unset(realm, monkeypatch):
    """Local realms need no audience mapper; production is required to set one."""
    monkeypatch.setattr("config.settings.keycloak_audience", "", raising=False)
    token = _token(realm["pem"], "key-1", aud="anything-at-all")
    payload = await auth.get_current_patient(_credentials(token))
    assert payload["sub"] == "patient-1"


def test_production_settings_require_an_audience():
    from config import Settings

    with pytest.raises(ValueError, match="KEYCLOAK_AUDIENCE"):
        Settings(
            environment="production",
            secret_key="x" * 64,
            minio_secret_key="not-the-default",
            sentry_dsn="https://example@sentry.invalid/1",
            keycloak_audience="",
        )


def test_production_settings_accept_a_configured_audience():
    from config import Settings

    settings = Settings(
        environment="production",
        secret_key="x" * 64,
        minio_secret_key="not-the-default",
        sentry_dsn="https://example@sentry.invalid/1",
        keycloak_audience=AUDIENCE,
    )
    assert settings.keycloak_audience == AUDIENCE


# ── The development bypass stays shut outside development ────────────────────

async def test_demo_token_is_not_honoured_in_production(realm):
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_patient(_credentials("demo-local-token"))
    assert exc.value.status_code == 401


async def test_demo_token_works_in_development(realm, monkeypatch):
    monkeypatch.setattr("config.settings.environment", "development", raising=False)
    payload = await auth.get_current_patient(_credentials("demo-local-token"))
    assert payload["sub"] == "demo-user"
