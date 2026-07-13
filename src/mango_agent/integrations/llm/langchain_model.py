"""LangChain adapter for the provider-independent model port."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from typing import Any, final

from langchain_core.exceptions import ContextOverflowError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.content import ImageContentBlock

from mango_agent.shared.domain.errors import (
    ForbiddenError,
    InternalError,
    MangoError,
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

RedactionHook = Callable[[str], str]

DATA_URL_PATTERN = re.compile(r"^data:image/(?P<media_type>[^;]+);base64,(?P<data>.+)$")


@final
class LangChainModelPort(ModelPort):
    """Invoke an injected LangChain chat model through Mango's model port."""

    def __init__(
        self,
        model: BaseChatModel,
        redaction_hook: RedactionHook | None = None,
    ) -> None:
        self._model = model
        self._redaction_hook = redaction_hook

    async def invoke(
        self,
        messages: tuple[Message | ToolResult, ...],
        tools: tuple[Tool, ...] = (),
        temperature: float | None = None,
    ) -> ModelResponse:
        langchain_messages = [self._to_langchain_message(message) for message in messages]
        invocation_kwargs: dict[str, Any] = {}
        if temperature is not None:
            invocation_kwargs["temperature"] = temperature

        try:
            if tools:
                runnable = self._model.bind_tools([self._to_langchain_tool(tool) for tool in tools])
                response = await runnable.ainvoke(langchain_messages, **invocation_kwargs)
            else:
                response = await self._model.ainvoke(langchain_messages, **invocation_kwargs)
        except MangoError:
            raise
        except Exception as exc:
            raise _translate_model_error(exc) from exc

        if not isinstance(response, AIMessage):
            raise InternalError("model returned an unsupported response type")
        return self._to_model_response(response)

    def _to_langchain_message(self, message: Message | ToolResult) -> BaseMessage:
        if isinstance(message, ToolResult):
            return ToolMessage(content=message.content, tool_call_id=message.id)

        content = self._apply_redaction(message.content)
        image = self._parse_image_data_url(content)
        message_type = _message_type(message.role)

        if image is None:
            return message_type(content=content)
        return message_type(content_blocks=[image])

    def _apply_redaction(self, content: str) -> str:
        if self._redaction_hook is None:
            return content
        return self._redaction_hook(content)

    def _parse_image_data_url(self, content: str) -> ImageContentBlock | None:
        match = DATA_URL_PATTERN.match(content)
        if not match:
            return None

        data = match.group("data")
        try:
            base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError("image data URL contains invalid base64 data") from exc

        return {
            "type": "image",
            "mime_type": f"image/{match.group('media_type')}",
            "base64": data,
        }

    def _to_langchain_tool(self, tool: Tool) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        }

    def _to_model_response(self, response: AIMessage) -> ModelResponse:
        tool_calls: list[ToolCall] = []
        for call in response.tool_calls:
            call_id = call.get("id")
            if not isinstance(call_id, str) or not call_id.strip():
                raise InternalError("model returned a tool call without an id")

            tool_calls.append(
                ToolCall(
                    id=call_id,
                    name=call["name"],
                    arguments=dict(call["args"]),
                )
            )

        input_tokens = (
            response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
        )
        output_tokens = (
            response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0
        )
        return ModelResponse(
            content=_response_text(response),
            tool_calls=tuple(tool_calls),
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )


def _message_type(role: str) -> type[HumanMessage] | type[AIMessage] | type[SystemMessage]:
    if role == "user":
        return HumanMessage
    if role == "assistant":
        return AIMessage
    if role == "system":
        return SystemMessage
    raise ValidationError(f"unsupported model message role: {role}")


def _response_text(response: AIMessage) -> str | None:
    if isinstance(response.content, str):
        return response.content

    text_parts = [
        block if isinstance(block, str) else block["text"]
        for block in response.content
        if isinstance(block, str)
        or (block.get("type") == "text" and isinstance(block.get("text"), str))
    ]
    return "\n".join(text_parts) if text_parts else None


def _translate_model_error(exc: Exception) -> MangoError:
    status_code = _status_code(exc)
    if status_code == 400 or isinstance(exc, (ContextOverflowError, ValueError)):
        return ValidationError("model request invalid")
    if status_code == 401:
        return UnauthorizedError("model authentication failed")
    if status_code == 403:
        return ForbiddenError("model invocation not permitted")
    if status_code == 408 or _exception_name_contains(exc, "timeout"):
        return InternalError("model invocation timed out")
    if _exception_name_contains(exc, "connection"):
        return InternalError("model invocation connection failed")
    if status_code == 429 or _exception_name_contains(exc, "ratelimit"):
        return InternalError("model rate limit exceeded")
    if status_code is not None and status_code >= 500:
        return InternalError("model provider unavailable")
    return InternalError("model invocation failed")


def _status_code(exc: Exception) -> int | None:
    for error in _exception_chain(exc):
        status_code = _integer_attribute(error, "status_code")
        if status_code is not None:
            return status_code

        response = _attribute(error, "response")
        status_code = _integer_attribute(response, "status_code")
        if status_code is not None:
            return status_code
    return None


def _exception_name_contains(exc: Exception, fragment: str) -> bool:
    return any(
        fragment in error_type.__name__.replace("_", "").lower()
        for error in _exception_chain(exc)
        for error_type in type(error).__mro__
    )


def _exception_chain(exc: Exception) -> tuple[BaseException, ...]:
    errors: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        errors.append(current)
        current = current.__cause__ or current.__context__
    return tuple(errors)


def _attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _integer_attribute(value: object, name: str) -> int | None:
    attribute = _attribute(value, name)
    if isinstance(attribute, int) and not isinstance(attribute, bool):
        return attribute
    return None
