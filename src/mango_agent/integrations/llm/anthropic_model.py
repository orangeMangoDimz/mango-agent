"""Anthropic adapter for the provider-independent model port."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import anthropic
from pydantic import SecretStr

from mango_agent.shared.domain.errors import (
    ForbiddenError,
    InternalError,
    UnauthorizedError,
    ValidationError,
)
from mango_agent.shared.ports.model import (
    Message,
    ModelPort,
    ModelResponse,
    Tool,
    ToolCall,
    ToolResult,
    Usage,
)

if TYPE_CHECKING:
    from anthropic.types import Message as AnthropicMessage

RedactionHook = Callable[[str], str]

DATA_URL_PATTERN = re.compile(r"^data:image/(?P<media_type>[^;]+);base64,(?P<data>.+)$")
DEFAULT_MAX_TOKENS = 1024


class AnthropicModelPort(ModelPort):
    """Anthropic model adapter using the async Anthropic client.

    Supports text, image, and tool-use invocations. Message content may be
    redacted before being sent to Anthropic by providing a ``RedactionHook``.
    For testing, ``fake_responses`` can be provided to bypass the network.

    Fake mode
    ---------
    When ``fake_responses`` is provided, the adapter never creates an Anthropic
    client and never calls the API. If ``fake_responses`` is a mapping, the
    adapter looks up the response by the first message content (falling back to
    a key of ``""``). If it is a sequence, the first response is returned for
    every invocation. This is useful for deterministic tests without credentials.
    """

    def __init__(
        self,
        model: str,
        api_key: SecretStr | str,
        redaction_hook: RedactionHook | None = None,
        fake_responses: Mapping[str, ModelResponse] | Sequence[ModelResponse] | None = None,
    ) -> None:
        if not model.strip():
            raise ValidationError("model name must not be empty")

        self._model = model
        self._redaction_hook = redaction_hook
        self._fake_responses = fake_responses

        if fake_responses is not None:
            self._client: anthropic.AsyncAnthropic | None = None
            return

        api_key_value = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not api_key_value:
            raise ValidationError("api_key must not be empty")

        self._client = anthropic.AsyncAnthropic(api_key=api_key_value)

    async def invoke(
        self,
        messages: tuple[Message | ToolResult, ...],
        tools: tuple[Tool, ...] = (),
        temperature: float | None = None,
    ) -> ModelResponse:
        normalized_messages = tuple(self._normalize_message(msg) for msg in messages)

        if self._client is None:
            return self._fake_response(normalized_messages)

        anthropic_messages = [self._to_anthropic_message(msg) for msg in normalized_messages]
        anthropic_tools = [self._to_anthropic_tool(tool) for tool in tools] or None

        create_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": anthropic_messages,
        }
        if anthropic_tools is not None:
            create_kwargs["tools"] = anthropic_tools
        if temperature is not None:
            create_kwargs["temperature"] = temperature

        try:
            response = await self._client.messages.create(**create_kwargs)
        except anthropic.APITimeoutError as exc:
            raise InternalError(f"model invocation timed out: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise InternalError(f"model invocation connection failed: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise UnauthorizedError(f"model authentication failed: {exc}") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ForbiddenError(f"model invocation not permitted: {exc}") from exc
        except anthropic.BadRequestError as exc:
            raise ValidationError(f"model request invalid: {exc}") from exc
        except anthropic.NotFoundError as exc:
            raise InternalError(f"model not found: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise InternalError(f"model rate limit exceeded: {exc}") from exc
        except anthropic.APIError as exc:
            raise InternalError(f"model invocation failed: {exc}") from exc

        return self._to_model_response(response)

    def _fake_response(self, messages: tuple[Message | ToolResult, ...]) -> ModelResponse:
        if isinstance(self._fake_responses, Mapping):
            key = messages[0].content if messages else ""
            response = self._fake_responses.get(key)
            if response is None:
                response = self._fake_responses.get("")
            if response is not None:
                return response
            raise InternalError("no fake response configured for the given prompt")

        if self._fake_responses:
            return self._fake_responses[0]
        raise InternalError("fake responses sequence is empty")

    def _normalize_message(self, msg: Message | ToolResult) -> Message | ToolResult:
        if isinstance(msg, ToolResult):
            return msg

        content = self._apply_redaction(msg.content)
        self._validate_image_data_url(content)
        return Message(role=msg.role, content=content)

    def _apply_redaction(self, content: str) -> str:
        if self._redaction_hook is None:
            return content
        return self._redaction_hook(content)

    def _validate_image_data_url(self, content: str) -> None:
        match = DATA_URL_PATTERN.match(content)
        if not match:
            return

        data = match.group("data")
        try:
            base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError("image data URL contains invalid base64 data") from exc

    def _to_anthropic_message(self, msg: Message | ToolResult) -> dict[str, Any]:
        if isinstance(msg, ToolResult):
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.id,
                        "content": msg.content,
                    }
                ],
            }

        image = self._parse_image_data_url(msg.content)
        if image is not None:
            return {"role": msg.role, "content": [image]}

        return {"role": msg.role, "content": [{"type": "text", "text": msg.content}]}

    def _parse_image_data_url(self, content: str) -> dict[str, Any] | None:
        match = DATA_URL_PATTERN.match(content)
        if not match:
            return None

        media_type = f"image/{match.group('media_type')}"
        data = match.group("data")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        }

    def _to_anthropic_tool(self, tool: Tool) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters_schema,
        }

    def _to_model_response(self, response: AnthropicMessage) -> ModelResponse:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )

        content = "\n".join(content_parts) if content_parts else None
        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return ModelResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            usage=usage,
        )
