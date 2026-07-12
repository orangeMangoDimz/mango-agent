from __future__ import annotations

import uuid
from types import MappingProxyType

import pytest

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.tracing import (
    RedactionCategory,
    RedactionPolicy,
    Span,
    SpanId,
    TracingPort,
    redact,
)


def test_span_id_is_typed_uuid() -> None:
    span_id = SpanId.generate()
    assert isinstance(span_id.value, uuid.UUID)


def test_span_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        Span(
            id=SpanId.generate(),
            name="   ",
            started_at=Timestamp.now(),
        )


def test_span_is_frozen() -> None:
    span = Span(
        id=SpanId.generate(),
        name="test",
        started_at=Timestamp.now(),
        correlation_id=uuid.uuid4(),
    )
    with pytest.raises(AttributeError):
        span.name = "changed"


def test_redaction_policy_is_frozen() -> None:
    policy = RedactionPolicy()
    with pytest.raises(AttributeError):
        policy.hooks = {}


def test_redact_applies_configured_hook() -> None:
    policy = RedactionPolicy(
        hooks=MappingProxyType({RedactionCategory.CREDENTIALS: lambda value: "[REDACTED]"})
    )
    assert redact("secret", RedactionCategory.CREDENTIALS, policy) == "[REDACTED]"


def test_redact_leaves_unconfigured_value_unchanged() -> None:
    policy = RedactionPolicy()
    assert redact("visible", RedactionCategory.CREDENTIALS, policy) == "visible"


def test_redact_ignores_other_categories() -> None:
    policy = RedactionPolicy(
        hooks=MappingProxyType({RedactionCategory.CREDENTIALS: lambda value: "[REDACTED]"})
    )
    assert redact("visible", RedactionCategory.FULL_TEXT, policy) == "visible"


def test_tracing_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        TracingPort()


async def test_fake_tracing_port() -> None:
    class FakeTracingPort(TracingPort):
        def __init__(self) -> None:
            self.spans: dict[SpanId, Span] = {}
            self.correlation_id: uuid.UUID | None = None
            self.attributes: dict[SpanId, dict[str, object]] = {}

        async def start_span(
            self,
            name: str,
            parent_id: SpanId | None = None,
            correlation_id: uuid.UUID | None = None,
        ) -> Span:
            span = Span(
                id=SpanId.generate(),
                name=name,
                started_at=Timestamp.now(),
                correlation_id=correlation_id,
            )
            self.spans[span.id] = span
            self.attributes[span.id] = {}
            return span

        async def end_span(self, span_id: SpanId) -> None:
            if span_id not in self.spans:
                raise ValueError("span not found")

        async def set_attribute(
            self,
            span_id: SpanId,
            key: str,
            value: object,
            redaction: RedactionPolicy | None = None,
        ) -> None:
            if span_id not in self.spans:
                raise ValueError("span not found")
            self.attributes[span_id][key] = value

        async def set_correlation_id(self, correlation_id: uuid.UUID) -> None:
            self.correlation_id = correlation_id

    port = FakeTracingPort()
    correlation_id = uuid.uuid4()
    span = await port.start_span("root", correlation_id=correlation_id)

    assert span.name == "root"
    assert span.correlation_id == correlation_id

    await port.end_span(span.id)
    await port.set_attribute(span.id, "key", "value")
    await port.set_correlation_id(correlation_id)

    assert port.attributes[span.id]["key"] == "value"
    assert port.correlation_id == correlation_id
