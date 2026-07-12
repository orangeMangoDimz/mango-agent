"""LangSmith adapter for the provider-independent tracing port."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, final
from uuid import UUID

from pydantic import SecretStr

from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import EntityId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.infrastructure import correlation
from mango_agent.shared.ports.tracing import (
    RedactionCategory,
    RedactionPolicy,
    Span,
    SpanId,
    TracingPort,
    redact,
)

if TYPE_CHECKING:
    from langsmith import Client


RUN_TYPE: Literal["chain"] = "chain"
METADATA_KEY = "metadata"

_CATEGORIZED_KEYS: Mapping[str, RedactionCategory] = {
    "full_text": RedactionCategory.FULL_TEXT,
    "image_derived_text": RedactionCategory.IMAGE_DERIVED_TEXT,
    "credentials": RedactionCategory.CREDENTIALS,
    "object_url": RedactionCategory.OBJECT_URL,
    "notes": RedactionCategory.NOTES,
}


@dataclass
class _SpanState:
    """In-memory state for a started span."""

    span: Span
    attributes: dict[str, object] = field(default_factory=dict)
    parent_id: SpanId | None = None


def _resolve_api_key(value: SecretStr | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        secret = value.get_secret_value()
        return secret if secret else None
    return value if value else None


def _infer_category(key: str) -> RedactionCategory | None:
    return _CATEGORIZED_KEYS.get(key.lower())


def _serialize_value(value: object) -> object:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, EntityId):
        return str(value.value)
    if isinstance(value, Timestamp):
        return value.value.isoformat()
    if isinstance(value, SecretStr):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return str(value)


def _serialize_attributes(attributes: Mapping[str, object]) -> dict[str, object]:
    return {key: _serialize_value(value) for key, value in attributes.items()}


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


@final
class LangSmithTracingPort(TracingPort):
    """Tracing adapter backed by LangSmith.

    The adapter is a clean no-op when ``enabled`` is ``False`` or the API key is
    missing: it still returns valid :class:`Span` objects and records
    attributes in memory, but never calls the LangSmith API.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        project_name: str | None = None,
        enabled: bool = False,
    ) -> None:
        self._project_name = project_name
        self._enabled = enabled
        self._api_key = _resolve_api_key(api_key)
        self._client: Client | None = None
        self._spans: dict[SpanId, _SpanState] = {}

        if self._enabled and self._api_key is not None:
            from langsmith import Client

            self._client = Client(api_key=self._api_key)

    def _state(self, span_id: SpanId) -> _SpanState:
        state = self._spans.get(span_id)
        if state is None:
            raise NotFoundError(f"span {span_id} not found")
        return state

    async def start_span(
        self,
        name: str,
        parent_id: SpanId | None = None,
        correlation_id: UUID | None = None,
    ) -> Span:
        correlation_id = correlation_id or correlation.get_correlation_id()
        span_id = SpanId.generate()
        started_at = Timestamp.now()
        span = Span(
            id=span_id,
            name=name,
            started_at=started_at,
            correlation_id=correlation_id,
        )
        self._spans[span_id] = _SpanState(span=span, parent_id=parent_id)

        if self._client is not None:
            metadata: dict[str, object] = {}
            if correlation_id is not None:
                metadata["correlation_id"] = str(correlation_id)
            await asyncio.to_thread(
                self._client.create_run,
                id=span_id.value,
                name=name,
                run_type=RUN_TYPE,
                project_name=self._project_name,
                parent_run_id=parent_id.value if parent_id is not None else None,
                start_time=started_at.value,
                inputs={},
                extra={METADATA_KEY: metadata},
            )

        return span

    async def end_span(self, span_id: SpanId) -> None:
        state = self._state(span_id)
        ended_at = _now_utc()
        duration_ms = int((ended_at - state.span.started_at.value).total_seconds() * 1000)
        state.attributes["duration_ms"] = duration_ms

        if self._client is not None:
            await asyncio.to_thread(
                self._client.update_run,
                run_id=span_id.value,
                end_time=ended_at,
                extra={METADATA_KEY: _serialize_attributes(state.attributes)},
            )

    async def set_attribute(
        self,
        span_id: SpanId,
        key: str,
        value: object,
        redaction: RedactionPolicy | None = None,
    ) -> None:
        state = self._state(span_id)
        category = _infer_category(key)
        if category is not None and redaction is not None and isinstance(value, str):
            value = redact(value, category, redaction)
        state.attributes[key] = value

        if self._client is not None:
            await asyncio.to_thread(
                self._client.update_run,
                run_id=span_id.value,
                extra={METADATA_KEY: _serialize_attributes(state.attributes)},
            )

    async def set_correlation_id(self, correlation_id: UUID) -> None:
        correlation.set_correlation_id(correlation_id)
