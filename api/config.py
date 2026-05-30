from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Email
    resend_api_key: str = ""

    # OncoKB
    oncokb_api_token: str = ""

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
        if env == "production" and v == "dev-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from the default value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        if self.environment == "production":
            if not self.sentry_dsn:
                import logging
                logging.getLogger("openoncology.config").warning(
                    "SENTRY_DSN is not set — errors in production will not be tracked"
                )
            if self.minio_secret_key == "password":
                raise ValueError("MINIO_SECRET_KEY must be changed from the default in production")
        return self


settings = Settings()
