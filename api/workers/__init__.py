"""
Celery app — shared broker configuration for all workers.
"""
from celery import Celery
from config import settings

celery_app = Celery(
    "openoncology",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "workers.genomic_worker.*": {"queue": "genomic"},
        "workers.ai_worker.*": {"queue": "ai"},
        "workers.notify_worker.*": {"queue": "notify"},
    },
)
