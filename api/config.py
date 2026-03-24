from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://openoncology:password@localhost:5432/openoncology"

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


settings = Settings()
