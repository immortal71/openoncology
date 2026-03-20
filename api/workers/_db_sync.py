"""
Synchronous DB session helper for Celery workers.
Celery tasks are synchronous — they cannot use async SQLAlchemy sessions.
This helper provides a regular sync session for worker use.
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings

# Convert async URL to sync for Celery workers
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")

_engine = create_engine(_sync_url, pool_pre_ping=True)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_session() -> Session:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
