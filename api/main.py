from contextlib import asynccontextmanager
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import asyncio as redis_asyncio
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, text

from config import settings
from database import engine, Base, AsyncSessionLocal
from middleware.audit import AuditMiddleware
from middleware.rate_limit import limiter
from middleware.logging_config import configure_logging
from routes import auth, submit, results, repurposing, marketplace, oncologist, webhook, pharma_admin, stripe_connect, campaign, gdpr
from routes.cohorts import router as cohorts_router
from routes.fhir import router as fhir_router
from routes.visualizations import router as viz_router

# ── Sentry error tracking ──────────────────────────────────────────────────────
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,  # never send PHI to Sentry
        )
except ImportError:
    pass  # sentry-sdk not installed

logger = logging.getLogger("openoncology.api")

# Configure structured logging as early as possible
configure_logging(
    log_level="DEBUG" if settings.environment == "development" else "INFO",
    json_logs=settings.environment != "development",
)


def _error_payload(request: Request, error: str, detail) -> dict:
    return {
        "error": error,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
    }


async def _seed_local_demo_data() -> None:
    from models.patient import Patient
    from models.submission import Submission, SubmissionStatus
    from models.mutation import Mutation, MutationClassification, OncoKBLevel
    from models.result import Result
    from models.bid import DrugRequest, DiscoveryStatus

    async with AsyncSessionLocal() as session:
        existing_patient = (await session.execute(
            select(Patient).where(Patient.keycloak_id == "demo-user")
        )).scalar_one_or_none()
        if existing_patient:
            return

        patient = Patient(
            keycloak_id="demo-user",
            email_hash="demo-local-user",
            country="US",
            consent_research_sharing=True,
            data_retention_days=365,
        )
        session.add(patient)
        await session.flush()

        submission = Submission(
            patient_id=patient.id,
            cancer_type="Lung adenocarcinoma",
            status=SubmissionStatus.complete,
        )
        session.add(submission)
        await session.flush()

        mutation = Mutation(
            submission_id=submission.id,
            gene="KRAS",
            hgvs_notation="p.G12D",
            mutation_type="missense",
            classification=MutationClassification.likely_pathogenic,
            oncokb_level=OncoKBLevel.level_4,
            is_targetable=True,
        )
        session.add(mutation)

        result = Result(
            submission_id=submission.id,
            has_targetable_mutation=True,
            target_gene="KRAS",
            summary_text="Local development seeded result.",
            plain_language_summary="This seeded result can be used to test custom-drug generation locally.",
            oncologist_reviewed=False,
        )
        session.add(result)
        await session.flush()

        demo_brief = {
            "mutation_profile": ["KRAS p.G12D", "TP53 p.R175H"],
            "design_rationale": "Local development seed brief.",
            "lead_candidates": [],
            "de_novo_candidates": [],
            "component_library": {"scaffolds": [], "fragments": []},
            "docking_summary": {
                "runs_attempted": 0,
                "used_mutation_specific_structure": False,
                "structure_path": None,
            },
        }

        seeded_request = DrugRequest(
            id="drq-e1367550",
            patient_id=patient.id,
            result_id=result.id,
            target_gene="KRAS",
            drug_spec="Seeded local development request.",
            discovery_status=DiscoveryStatus.complete,
            discovery_brief=demo_brief,
            is_open=True,
        )
        session.add(seeded_request)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Production safety guards ───────────────────────────────────────────
    if settings.environment == "production":
        if settings.secret_key == "dev-secret-key-change-in-production":
            raise RuntimeError("SECRET_KEY must be set to a secure value in production")
        if any("localhost" in o or "127.0.0.1" in o for o in settings.cors_allow_origins):
            raise RuntimeError("CORS_ALLOW_ORIGINS contains localhost in production — lock it down")
    # Keep schema bootstrapping opt-in so development does not hide migration drift.
    if settings.environment == "development" and settings.bootstrap_schema_in_dev:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        if settings.local_dev_seed_data:
            await _seed_local_demo_data()
    yield
    await engine.dispose()


app = FastAPI(
    title="OpenOncology API",
    description="Open-source precision cancer medicine platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# SlowAPI rate limiter state
app.state.limiter = limiter

# ── Prometheus metrics ────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_client import Counter, Histogram
    Instrumentator(excluded_handlers=["/health", "/ready", "/metrics"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    MUTATIONS_PROCESSED = Counter(
        "openoncology_mutations_processed_total",
        "Total mutations analysed by the AI pipeline",
        ["oncokb_level"],
    )
    PIPELINE_DURATION = Histogram(
        "openoncology_genomic_pipeline_seconds",
        "End-to-end genomic pipeline duration in seconds",
        ["cancer_type"],
    )
except ImportError:
    pass  # prometheus-fastapi-instrumentator not installed


@app.middleware("http")
async def add_request_context_and_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "request.failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": elapsed_ms,
            },
        )
        raise

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request.completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
        },
    )
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    if settings.environment == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    return response

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=_error_payload(request, "rate_limit_exceeded", "Rate limit exceeded. Please slow down."),
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        payload = {
            "error": str(exc.detail.get("error") or "http_error"),
            "detail": exc.detail.get("detail") or "Request failed.",
            "request_id": exc.detail.get("request_id") or getattr(request.state, "request_id", None),
        }
    else:
        payload = _error_payload(request, "http_error", str(exc.detail) if exc.detail is not None else "Request failed.")
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "request.unhandled_exception",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content=_error_payload(request, "internal_server_error", "Internal server error."),
    )

app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(submit.router)
app.include_router(results.router)
app.include_router(repurposing.router)
app.include_router(marketplace.router)
app.include_router(campaign.router)
app.include_router(oncologist.router)
app.include_router(webhook.router)
app.include_router(pharma_admin.router)
app.include_router(stripe_connect.router)
app.include_router(gdpr.router)
# Phase 2: multi-cohort study browser
app.include_router(cohorts_router)
# Phase 3: visualisations (lollipop, survival, co-occurrence)
app.include_router(viz_router)
# Phase 6: FHIR R4 export
app.include_router(fhir_router)

# Phase 4: GraphQL API (mounted only when strawberry is installed)
try:
    from graphql import create_graphql_router
    from database import get_db
    app.include_router(create_graphql_router(get_db), prefix="/graphql")
except ImportError:
    pass  # strawberry-graphql not installed — GraphQL endpoint disabled


@app.get("/health")
async def health():
    return {"status": "ok", "service": "openoncology-api"}


@app.get("/ready")
async def ready() -> JSONResponse:
    checks = {
        "database": False,
        "redis": False,
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    redis_client = None
    try:
        redis_client = redis_asyncio.from_url(settings.redis_url)
        checks["redis"] = bool(await redis_client.ping())
    except Exception:
        checks["redis"] = False
    finally:
        if redis_client is not None:
            await redis_client.close()

    overall_ready = all(checks.values())
    status_code = 200 if overall_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if overall_ready else "degraded",
            "service": "openoncology-api",
            "checks": checks,
        },
    )
