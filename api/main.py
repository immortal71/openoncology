from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from config import settings
from database import engine, Base, AsyncSessionLocal
from middleware.audit import AuditMiddleware
from middleware.rate_limit import limiter
from routes import auth, submit, results, repurposing, marketplace, oncologist, webhook, pharma_admin, stripe_connect, campaign, gdpr


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
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# SlowAPI rate limiter state
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please slow down."})

app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "openoncology-api"}
