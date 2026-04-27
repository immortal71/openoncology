"""
Celery app — shared broker configuration for all workers.
"""
import socket
from urllib.parse import urlparse

from celery import Celery
from config import settings

def _redis_reachable(redis_url: str) -> bool:
    parsed = urlparse(redis_url)
    host = parsed.hostname
    port = parsed.port or 6379
    if not host:
        return False

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


_local_inline_tasks = settings.environment == "development" and not _redis_reachable(settings.redis_url)

celery_app = Celery(
    "openoncology",
    broker="memory://" if _local_inline_tasks else settings.redis_url,
    backend="cache+memory://" if _local_inline_tasks else settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=_local_inline_tasks,
    task_eager_propagates=True,
    task_routes={
        "workers.genomic_worker.*": {"queue": "genomic"},
        "workers.ai_worker.*": {"queue": "ai"},
        "workers.custom_drug_worker.*": {"queue": "ai"},
        "workers.notify_worker.*": {"queue": "notify"},
    },
)
