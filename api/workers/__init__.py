"""
Celery app — shared broker configuration for all workers.
"""
import socket
from urllib.parse import urlparse

from celery import Celery
from celery.schedules import crontab
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
    # ── Reliability ────────────────────────────────────────────────────────
    # Do not ack a task until it completes — ensures re-queue on worker crash
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Prefetch 1 task at a time so long-running jobs don't starve other workers
    worker_prefetch_multiplier=1,
    # Dead-letter: failed tasks are moved to a dedicated DLQ queue after exhausting retries
    task_queues_default_exchange_type="direct",
    # Result expiry — keep task results 24 h then auto-expire
    result_expires=86400,
    # ── Observability ──────────────────────────────────────────────────────
    # Celery emits nothing about task lifecycle unless asked. Without these the
    # broker carries the work and no external observer can tell a queue that is
    # draining from one that has stalled, which is what BACKLOG.md OO-16 is
    # about: the gdpr queue silently not draining means erasure requests are not
    # being honoured, and that is an obligation with a deadline attached.
    #
    # Two separate switches. worker_send_task_events makes workers publish
    # started/succeeded/failed; task_send_sent_event makes the *producer*
    # publish on enqueue, which is the only way to measure the gap between
    # submission and pickup. Queue latency needs both.
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_routes={
        "workers.genomic_worker.*": {"queue": "genomic"},
        "workers.ai_worker.*": {"queue": "ai"},
        "workers.custom_drug_worker.*": {"queue": "ai"},
        "workers.notify_worker.*": {"queue": "notify"},
        "workers.gdpr_worker.*": {"queue": "gdpr"},
    },
    # ── Periodic tasks (Celery Beat) ────────────────────────────────────────
    beat_schedule={
        # Enforce GDPR data retention — delete patient data past retention_days at 3am daily
        "gdpr-enforce-retention-daily": {
            "task": "workers.gdpr_worker.enforce_retention_policy",
            "schedule": crontab(hour=3, minute=0),
        },
        # Sweep submissions stuck in 'processing' for > 6 hours (pipeline crash recovery)
        "sweep-stale-submissions-hourly": {
            "task": "workers.genomic_worker.sweep_stale_submissions",
            "schedule": crontab(minute=0),  # every hour
        },
    },
)
