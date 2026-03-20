from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from config import settings
from database import engine, Base
from middleware.audit import AuditMiddleware
from middleware.rate_limit import limiter
from routes import auth, submit, results, repurposing, marketplace, crowdfund, oncologist, webhook, pharma_admin, stripe_connect, campaign, gdpr


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (dev only — use Alembic in prod)
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(submit.router)
app.include_router(results.router)
app.include_router(repurposing.router)
app.include_router(marketplace.router)
app.include_router(crowdfund.router)
app.include_router(campaign.router)
app.include_router(oncologist.router)
app.include_router(webhook.router)
app.include_router(pharma_admin.router)
app.include_router(stripe_connect.router)
app.include_router(gdpr.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "openoncology-api"}
