from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

_engine_kwargs: dict = {
    "echo": settings.environment == "development",
    "pool_pre_ping": True,
}
if settings.database_url.startswith("sqlite+"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL production pool — tuned for 2–4 API replicas on a typical RDS/Cloud SQL instance
    _engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,   # recycle connections after 30 min to avoid stale TCP
    })

engine = create_async_engine(
    settings.database_url,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
