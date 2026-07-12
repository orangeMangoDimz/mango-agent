"""Prometheus metrics registry for Mango Agent infrastructure."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

_MESSAGE_LABELS = ["channel", "command", "outcome"]
_INFRA_LABELS = ["operation"]
_PROVIDER_LABELS = ["provider", "outcome"]


class MetricsRegistry:
    """Prometheus metrics surfaced by the bot and background workers."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or CollectorRegistry()
        self.messages = Counter(
            "mango_messages_total",
            "Inbound provider messages processed",
            _MESSAGE_LABELS,
            registry=self._registry,
        )
        self.message_latency = Histogram(
            "mango_message_latency_seconds",
            "End-to-end message processing latency",
            ["channel", "command"],
            registry=self._registry,
        )
        self.db_operations = Counter(
            "mango_db_operations_total",
            "Postgres operations",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.db_errors = Counter(
            "mango_db_operation_errors_total",
            "Postgres operation failures",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.db_latency = Histogram(
            "mango_db_operation_latency_seconds",
            "Postgres operation latency",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.redis_operations = Counter(
            "mango_redis_operations_total",
            "Redis operations",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.redis_errors = Counter(
            "mango_redis_operation_errors_total",
            "Redis operation failures",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.redis_latency = Histogram(
            "mango_redis_operation_latency_seconds",
            "Redis operation latency",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.r2_operations = Counter(
            "mango_r2_operations_total",
            "R2 object operations",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.r2_errors = Counter(
            "mango_r2_operation_errors_total",
            "R2 object operation failures",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.r2_latency = Histogram(
            "mango_r2_operation_latency_seconds",
            "R2 object operation latency",
            _INFRA_LABELS,
            registry=self._registry,
        )
        self.provider_delivery = Counter(
            "mango_provider_delivery_total",
            "Outbound provider delivery attempts",
            _PROVIDER_LABELS,
            registry=self._registry,
        )
        self.provider_delivery_latency = Histogram(
            "mango_provider_delivery_latency_seconds",
            "Outbound provider delivery latency",
            ["provider"],
            registry=self._registry,
        )
        self.agent_executions = Counter(
            "mango_agent_executions_total",
            "Agent executions",
            ["command", "outcome"],
            registry=self._registry,
        )
        self.agent_execution_latency = Histogram(
            "mango_agent_execution_latency_seconds",
            "Agent execution latency",
            ["command"],
            registry=self._registry,
        )
        self.proposals_expired = Counter(
            "mango_proposals_expired_total",
            "Proposals that expired before approval",
            ["command"],
            registry=self._registry,
        )
        self.duplicate_events = Counter(
            "mango_duplicate_events_total",
            "Duplicate provider events or operations deduplicated",
            ["kind"],
            registry=self._registry,
        )

    def start_server(self, port: int = 8000) -> None:
        """Expose metrics on a Prometheus scrape endpoint."""
        start_http_server(port, registry=self._registry)


METRICS = MetricsRegistry()


__all__ = ["METRICS", "MetricsRegistry"]
