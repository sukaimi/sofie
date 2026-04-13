"""Celery app configuration for async job processing.

Jobs are submitted via WebSocket, queued in Redis, and processed
by a single Celery worker (sequential, per POC constraint).
"""

from celery import Celery

from backend.config import settings

app = Celery(
    "sofie",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,  # Sequential processing — POC constraint
    task_acks_late=True,  # Re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1,
)
