"""Provider-independent model port.

The value types below are intentionally generic: they describe *what* the
agent needs from a language model (messages, tool definitions, tool calls,
usage) without coupling to any provider SDK. Concrete adapters map these
values to Anthropic, OpenAI, or other providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError


@final
@dataclass(frozen=True, slots=True)
class Message:
    """A single turn in a model conversation."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValidationError("message role must not be empty")


@final
@dataclass(frozen=True, slots=True)
class Tool:
    """A tool that can be made available to a model during invocation."""

    name: str
    description: str
    parameters_schema: dict[str, object]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("tool name must not be empty")
        if not isinstance(self.parameters_schema, dict):
            raise ValidationError("tool parameters_schema must be a dict")


@final
@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: dict[str, object]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("tool call id must not be empty")
        if not self.name.strip():
            raise ValidationError("tool call name must not be empty")


@final
@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result of executing a tool call, returned to the model as a message."""

    id: str
    content: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("tool result id must not be empty")


@final
@dataclass(frozen=True, slots=True)
class Usage:
    """Token usage reported by the model for a single invocation."""

    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValidationError("input_tokens must be non-negative")
        if self.output_tokens < 0:
            raise ValidationError("output_tokens must be non-negative")


@final
@dataclass(frozen=True, slots=True)
class ModelResponse:
    """Structured, provider-independent response from a model invocation.

    Model output is treated as untrusted input: callers must validate content
    and tool call arguments against the application's structured input contracts
    before acting on them.
    """

    content: str | None
    tool_calls: tuple[ToolCall, ...]
    usage: Usage


class ModelPort(ABC):
    """Abstract port for invoking a language model."""

    @abstractmethod
    async def invoke(
        self,
        messages: tuple[Message | ToolResult, ...],
        tools: tuple[Tool, ...] = (),
        temperature: float | None = None,
    ) -> ModelResponse:
        """Invoke the model and return a structured response."""
