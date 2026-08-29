from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Environments where the hardening checks below are deliberately relaxed, because
# they hold no real data and are not reachable from outside.
#
# The list is of the RELAXED ones on purpose. Every guard used to be written as
# `environment == "production"`, so `staging` fell into a third state with the
# development conveniences off and the safety checks off as well: it accepted the
# literal default SECRET_KEY, the default MinIO password, and no audience claim.
# It failed open and silently, which is the wrong direction for the one
# environment that most resembles production.
#
# Keyed this way, an unrecognised value gets the guards rather than losing them,
# so a typo like "prod" or "Production" is hardened rather than wide open.
_RELAXED_ENVIRONMENTS = {"development", "test"}


def is_hardened(environment: str) -> bool:
    """True for any environment that is not explicitly a local or CI one."""
    return (environment or "").strip().lower() not in _RELAXED_ENVIRONMENTS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    cors_allow_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Database
    database_url: str = "sqlite+aiosqlite:///./openoncology_dev.db"
    bootstrap_schema_in_dev: bool = True
    local_dev_seed_data: bool = True

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "openoncology_admin"
    minio_secret_key: str = "password"
    minio_secure: bool = False

    # Bucket names
    bucket_raw: str = "openoncology-raw"
    bucket_vcf: str = "openoncology-vcf"
    bucket_reports: str = "openoncology-reports"
    local_storage_dir: str = "./local_storage"

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "openoncology"
    keycloak_client_id: str = "openoncology-api"
    keycloak_client_secret: str = ""
    keycloak_admin_password: str = "admin"  # Keycloak admin-cli password

    # Expected `aud` claim. Empty disables the audience check, which is what the
    # code did unconditionally before: it passed audience="account" and then set
    # verify_aud False, so a token minted for any other client in the realm
    # verified against every protected route. Empty is tolerated outside
    # production so a local realm needs no extra mapper; production requires it,
    # enforced below.
    #
    # Keycloak does not put the client id in `aud` by default — it goes in
    # `azp`, and `aud` is "account". Setting this means adding an audience
    # mapper to the client, which is the documented way round and the only one
    # that makes the claim mean anything.
    keycloak_audience: str = ""

    # Expected `iss` claim. Empty derives it from keycloak_url and the realm.
    # Set it explicitly wherever the URL the API dials differs from the hostname
    # Keycloak signs with, which is the normal case in a cluster: the API talks
    # to the internal Service while tokens carry the public ingress hostname.
    keycloak_issuer: str = ""

    # How long a fetched JWKS is reused. A `kid` miss forces a refresh before
    # the TTL lapses, so this bounds staleness for revoked keys rather than
    # delaying rotation pickup.
    keycloak_jwks_cache_seconds: int = 300
    keycloak_jwks_timeout_seconds: float = 5.0

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Email
    resend_api_key: str = ""

    # OncoKB
    oncokb_api_token: str = ""

    # Degraded-evidence policy (risk_analysis.md F4, open action 4).
    #
    # When the actionability table resolves to the undated built-in static
    # table, recommendations are still produced, from evidence of unknown
    # currency. Whether that should be allowed is a policy decision rather than
    # a code one, so it is a setting rather than a hardcoded branch.
    #
    # Default False: this is research-use software, and a hard refusal would
    # remove a research capability in order to prevent a clinical harm that
    # research use does not carry. It MUST be True for any clinical deployment.
    #
    # False does not mean silent. A degraded evidence base is stamped on the
    # result and rendered at the top of the report either way. This setting only
    # decides whether recommendations are withheld as well as flagged.
    require_current_evidence: bool = False

    # Merge CIViC level A/B predictive evidence into the actionability table,
    # capped at LEVEL_3B and never overriding an OncoKB entry.
    #
    # OncoKB's public dumps need a token this deployment may not have, and
    # without one the table is the undated built-in set of ~335 entries. That
    # mattered less when the ranker scored a broad repurposing pool; it matters
    # more now that candidate_pool_policy defaults to evidence_first and the
    # table decides what is recommended wherever it has an answer.
    #
    # Off by default: widening the evidence table changes which drugs can be
    # recommended, and that should be a deliberate act rather than a default.
    civic_supplement_enabled: bool = False

    # Which candidates are eligible to be ranked (risk_analysis.md, and
    # docs/BENCHMARK_NCI_MATCH.md for the measurements).
    #
    #   tier2           rank everything the repurposing sources returned, with
    #                   evidence-table levels stamped on. Current behaviour.
    #   evidence_first  when the actionability table has an answer for the
    #                   variant, rank only those drugs; fall back to the full
    #                   repurposing pool when it does not.
    #
    # The two differ only where the table has something to say. On the
    # FDA-label answer key, which is independent of every source this engine
    # reads, evidence_first scored +15.1 points on Precision@3, 95% CI
    # [5.6, 26.2], 7 wins to 0, sign test p = 0.016; on NCI-MATCH arms it
    # turned 12 exact hits into 15.
    #
    # Default flipped to evidence_first on 2026-08-19, as a maintainer decision
    # on the evidence above rather than a default a benchmark set for itself.
    #
    # What improves is drug identity within the top three on approved
    # indications. What is NOT established is any patient outcome; no benchmark
    # in this repository measures one.
    #
    # The residual risk runs the other way from the gain. evidence_first replaces
    # the pool rather than reordering it, so where the table holds a STALE or
    # WRONG answer the broader repurposing pool no longer appears underneath it.
    # Every measured gene was an approved indication, where a curated table
    # should be right; emerging and off-label biomarkers are the untested regime.
    # Set this back to "tier2" to restore the previous behaviour exactly.
    candidate_pool_policy: str = "evidence_first"

    # Consecutive static-fallback resolutions before the log escalates from
    # WARNING to ERROR. One fallback is a blip; a sustained run means the
    # evidence source has been unreachable for a while and nobody noticed.
    degraded_evidence_alert_after: int = 3

    # OpenAI (for plain-language LLM summaries)
    openai_api_key: str = ""

    # COSMIC (Catalogue of Somatic Mutations in Cancer)
    cosmic_email: str = ""
    cosmic_password: str = ""

    # Observability
    sentry_dsn: str = ""  # Set to Sentry DSN in production to enable error tracking

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str, info) -> str:
        env = (info.data or {}).get("environment", "development")
        if is_hardened(env) and v == "dev-secret-key-change-in-production":
            raise ValueError(
                f"SECRET_KEY must be changed from the default value in {env!r}. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        # Applies to staging as much as production. Staging for a system holding
        # patient genomic data is not a scratch environment.
        if is_hardened(self.environment):
            if not self.sentry_dsn:
                import logging
                logging.getLogger("openoncology.config").warning(
                    "SENTRY_DSN is not set — errors in production will not be tracked"
                )
            if self.minio_secret_key == "password":
                raise ValueError("MINIO_SECRET_KEY must be changed from the default in production")
            if not self.keycloak_audience.strip():
                raise ValueError(
                    "KEYCLOAK_AUDIENCE must be set in production. Without it the `aud` "
                    "claim is not checked, and a token issued to any other client in the "
                    "realm authenticates against every protected route. Add an audience "
                    "mapper to the Keycloak client and set this to the value it emits."
                )
        if self.environment == "development" and self.sentry_dsn:
            raise ValueError(
                "ENVIRONMENT is 'development' but SENTRY_DSN is set — this looks like a "
                "production deploy with ENVIRONMENT misconfigured. Set ENVIRONMENT=production "
                "(or unset SENTRY_DSN if this really is a dev environment)."
            )
        return self


settings = Settings()
