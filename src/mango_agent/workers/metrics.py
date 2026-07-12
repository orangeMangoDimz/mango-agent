"""Prometheus metrics for the attachment cleanup worker."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

from mango_agent.modules.attachments.application.cleanup import CleanupSummary


class CleanupMetrics:
    """Records attachment cleanup metrics to a Prometheus registry."""

    def __init__(self) -> None:
        self._attachments_cleaned = Counter(
            "mango_attachments_cleaned_total",
            "Attachments permanently deleted",
            ["status"],
        )
        self._cleanup_pending_gauge = Gauge(
            "mango_attachments_cleanup_pending",
            "Attachments awaiting cleanup after the last run",
        )
        self._orphaned_attachments = Gauge(
            "mango_orphaned_attachments_pending",
            "Attachment orphan events awaiting cleanup",
        )
        self._cleanup_failures = Counter(
            "mango_attachment_cleanup_failures_total",
            "Attachment cleanup attempts that failed",
            ["kind"],
        )

    def record(self, summary: CleanupSummary) -> None:
        self._attachments_cleaned.labels(status="deleted").inc(summary.deleted)
        self._attachments_cleaned.labels(status="cleanup_pending").inc(summary.cleanup_pending)
        self._cleanup_pending_gauge.set(summary.attachments_found - summary.deleted)
        self._orphaned_attachments.set(summary.orphan_events_found - summary.orphan_processed)
        self._cleanup_failures.labels(kind="orphan").inc(summary.orphan_failed)
