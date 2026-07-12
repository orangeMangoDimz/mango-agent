"""Provider-independent tracing port.

This port defines the primitives an adapter needs to record spans, attributes,
and correlation IDs. Sensitive values can be redacted by the concrete adapter
using a ``RedactionPolicy``; the port itself keeps attribute values as plain
objects so it stays provider-independent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import final
from uuid import UUID

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import EntityId
from mango_agent.shared.domain.value_objects import Timestamp


class RedactionCategory(StrEnum):
    """Kinds of sensitive values that an adapter may redact."""

    FULL_TEXT = "full_text"
    IMAGE_DERIVED_TEXT = "image_derived_text"
    CREDENTIALS = "credentials"
    OBJECT_URL = "object_url"
    NOTES = "notes"


type RedactionHook = Callable[[str], str]


@final
@dataclass(frozen=True, slots=True)
class RedactionPolicy:
    """Maps redaction categories to hooks."""

    hooks: Mapping[RedactionCategory, RedactionHook] = field(
        default_factory=lambda: MappingProxyType({})
    )


@final
class SpanId(EntityId):
    """Identifies a tracing span."""


@final
@dataclass(frozen=True, slots=True)
class Span:
    """A started span, returned by ``TracingPort.start_span``."""

    id: SpanId
    name: str
    started_at: Timestamp
    correlation_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("span name must not be empty")


class TracingPort(ABC):
    """Abstract port for tracing and correlation."""

    @abstractmethod
    async def start_span(
        self,
        name: str,
        parent_id: SpanId | None = None,
        correlation_id: UUID | None = None,
    ) -> Span:
        """Start a new span and return it."""

    @abstractmethod
    async def end_span(self, span_id: SpanId) -> None:
        """Mark a previously started span as finished."""

    @abstractmethod
    async def set_attribute(
        self,
        span_id: SpanId,
        key: str,
        value: object,
        redaction: RedactionPolicy | None = None,
    ) -> None:
        """Set an attribute on a span, optionally redacting sensitive values."""

    @abstractmethod
    async def set_correlation_id(self, correlation_id: UUID) -> None:
        """Set the active correlation ID for the current execution scope."""


def redact(value: str, category: RedactionCategory, policy: RedactionPolicy) -> str:
    """Apply a redaction hook for ``category`` if one is configured."""

    hook = policy.hooks.get(category)
    if hook is None:
        return value
    return hook(value)
