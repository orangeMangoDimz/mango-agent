"""Celery task for attachment cleanup."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mango_agent.workers.celery_app import celery_app
from mango_agent.workers.cleanup import run_cleanup
from mango_agent.workers.metrics import CleanupMetrics

if TYPE_CHECKING:
    from celery import Task

_metrics = CleanupMetrics()


@celery_app.task(bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def cleanup_attachments(self: Task) -> None:
    """Hourly task that cleans up rejected/expired/orphaned attachments."""
    try:
        summary = asyncio.run(run_cleanup())
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
        raise
    _metrics.record(summary)
