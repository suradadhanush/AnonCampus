from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "anoncampus",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.score_tasks",
        "app.tasks.cluster_tasks",
        "app.tasks.trust_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=30,
    worker_prefetch_multiplier=1,
    task_track_started=True,

    beat_schedule={
        "daily-trust-decay": {
            "task": "app.tasks.trust_tasks.apply_trust_decay",
            "schedule": 86400.0,
        },
        "daily-recluster": {
            "task": "app.tasks.cluster_tasks.daily_recluster",
            "schedule": 86400.0,
        },
        "hourly-dormant-check": {
            "task": "app.tasks.cluster_tasks.check_dormant_clusters",
            "schedule": 3600.0,
        },
        "hourly-idempotency-cleanup": {
            "task": "app.tasks.score_tasks.cleanup_expired_idempotency_keys",
            "schedule": 3600.0,
        },
        "daily-refresh-token-cleanup": {
            "task": "app.tasks.score_tasks.cleanup_expired_refresh_tokens",
            "schedule": 86400.0,
        },
    },
)
