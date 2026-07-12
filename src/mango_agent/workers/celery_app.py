"""Celery application for background tasks."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from mango_agent.shared.infrastructure.config import load_worker_config
from mango_agent.shared.infrastructure.logging import configure_logging

config = load_worker_config()
configure_logging(config.logging)

redis_url = config.redis.redis_url.get_secret_value()

celery_app = Celery(
    "mango_agent",
    broker=redis_url,
    backend=redis_url,
    include=["mango_agent.workers.attachment_cleanup"],
)

celery_app.conf.beat_schedule = {
    "cleanup-attachments-hourly": {
        "task": "mango_agent.workers.attachment_cleanup.cleanup_attachments",
        "schedule": crontab(minute=0),
    },
}
