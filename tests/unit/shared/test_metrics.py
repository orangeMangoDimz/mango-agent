"""Unit tests for the Prometheus metrics registry."""

from __future__ import annotations

from prometheus_client import CollectorRegistry

from mango_agent.shared.infrastructure.metrics import MetricsRegistry


def test_metrics_registry_counts() -> None:
    registry = CollectorRegistry()
    metrics = MetricsRegistry(registry)
    metrics.messages.labels(channel="telegram", command="test", outcome="success").inc()
    metrics.messages.labels(channel="telegram", command="test", outcome="success").inc()
    metrics.messages.labels(channel="discord", command="test", outcome="error").inc()

    family = metrics.messages.collect()[0]
    samples = [
        sample
        for sample in family.samples
        if sample.name == "mango_messages_total" and sample.value > 0
    ]
    assert len(samples) == 2
    values = {tuple(sorted(sample.labels.items())): sample.value for sample in samples}
    assert values[("channel", "telegram"), ("command", "test"), ("outcome", "success")] == 2.0
    assert values[("channel", "discord"), ("command", "test"), ("outcome", "error")] == 1.0
