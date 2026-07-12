"""Shared ports for cross-cutting concerns and infrastructure abstractions."""

from __future__ import annotations

from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository
from mango_agent.shared.ports.model import (
    Message,
    ModelPort,
    ModelResponse,
    Tool,
    ToolCall,
    ToolResult,
    Usage,
)
from mango_agent.shared.ports.tracing import (
    RedactionCategory,
    RedactionPolicy,
    Span,
    SpanId,
    TracingPort,
    redact,
)
from mango_agent.shared.ports.unit_of_work import UnitOfWork

__all__ = [
    "ActorScope",
    "IdempotencyKey",
    "IdempotencyRepository",
    "Message",
    "ModelPort",
    "ModelResponse",
    "RedactionCategory",
    "RedactionPolicy",
    "Span",
    "SpanId",
    "Tool",
    "ToolCall",
    "ToolResult",
    "TracingPort",
    "UnitOfWork",
    "Usage",
    "redact",
]
