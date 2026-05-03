"""Shared pytest fixtures for FastAPI route integration tests.

Uses an in-memory SQLite database and overrides:
  - get_db  → async SQLite session
  - get_current_patient → fixed demo payload (no Keycloak needed)
  - rate limiter → disabled (always allows)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

# ── Import the app after sys.path is set ─────────────────────────────────────
from main import app
from database import Base, get_db
from routes.auth import get_current_patient
from middleware.rate_limit import limiter

# ── In-memory SQLite engine for tests ────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
_TestSessionLocal = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once per test session."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Truncate all rows before each test to ensure isolation."""
    async with _test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def db_session():
    """Provide a clean async DB session per test (auto-rollback)."""
    async with _TestSessionLocal() as session:
        yield session
        await session.rollback()


# ── Override dependencies ─────────────────────────────────────────────────────

_DEMO_TOKEN_PAYLOAD = {
    "sub": "test-user-123",
    "email": "patient@test.openoncology.local",
    "name": "Test Patient",
    "realm_access": {"roles": ["patient"]},
}


async def _override_get_db():
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _override_get_current_patient():
    return _DEMO_TOKEN_PAYLOAD


@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP test client with dependency overrides."""
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_patient] = _override_get_current_patient
    # Disable rate limiting in tests
    limiter._storage = None  # type: ignore[assignment]
    app.state.limiter = limiter

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_patient(db_session):
    """Insert a Patient row matching the test token's keycloak_id."""
    from models.patient import Patient

    patient = Patient(
        keycloak_id="test-user-123",
        email_hash="test-patient-hash",
        country="US",
        consent_research_sharing=True,
        data_retention_days=365,
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)
    return patient


@pytest_asyncio.fixture
async def seeded_submission(db_session, seeded_patient):
    """Insert a complete Submission + Result + Mutation for the test patient."""
    from models.submission import Submission, SubmissionStatus
    from models.mutation import Mutation, MutationClassification, OncoKBLevel
    from models.result import Result

    submission = Submission(
        patient_id=seeded_patient.id,
        cancer_type="Lung adenocarcinoma",
        status=SubmissionStatus.complete,
    )
    db_session.add(submission)
    await db_session.flush()

    mutation = Mutation(
        submission_id=submission.id,
        gene="EGFR",
        hgvs_notation="p.L858R",
        mutation_type="missense",
        classification=MutationClassification.likely_pathogenic,
        oncokb_level=OncoKBLevel.level_1,
        is_targetable=True,
    )
    db_session.add(mutation)

    result = Result(
        submission_id=submission.id,
        has_targetable_mutation=True,
        target_gene="EGFR",
        summary_text="EGFR L858R detected — erlotinib / osimertinib indicated.",
        plain_language_summary="Your tumour has a mutation in the EGFR gene.",
        oncologist_reviewed=False,
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(submission)
    return submission
