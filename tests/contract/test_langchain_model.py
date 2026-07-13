"""Deterministic contract tests for LangChainModelPort."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.exceptions import ContextOverflowError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import PrivateAttr

from mango_agent.integrations.llm.langchain_model import LangChainModelPort
from mango_agent.shared.domain.errors import (
    ForbiddenError,
    InternalError,
    MangoError,
    UnauthorizedError,
    ValidationError,
)
from mango_agent.shared.ports.model import Message, Tool, ToolCall, ToolResult, Usage

TINY_PNG_DATA = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
TINY_PNG = f"data:image/png;base64,{TINY_PNG_DATA}"


class RecordingChatModel(BaseChatModel):
    """Minimal BaseChatModel fake that records the LangChain adapter boundary."""

    _response: AIMessage = PrivateAttr()
    _exception: Exception | None = PrivateAttr()
    _calls: list[tuple[list[BaseMessage], dict[str, Any]]] = PrivateAttr(default_factory=list)
    _bound_tools: list[Any] = PrivateAttr(default_factory=list)

    def __init__(
        self,
        response: AIMessage | None = None,
        exception: Exception | None = None,
    ) -> None:
        super().__init__()
        self._response = response or AIMessage(content="ok")
        self._exception = exception

    @property
    def _llm_type(self) -> str:
        return "recording-chat-model"

    @property
    def calls(self) -> list[tuple[list[BaseMessage], dict[str, Any]]]:
        return self._calls

    @property
    def bound_tools(self) -> list[Any]:
        return self._bound_tools

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self._bound_tools = list(tools)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._result(messages, kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._result(messages, kwargs)

    def _result(self, messages: list[BaseMessage], kwargs: dict[str, Any]) -> ChatResult:
        self._calls.append((messages, kwargs))
        if self._exception is not None:
            raise self._exception
        return ChatResult(generations=[ChatGeneration(message=self._response)])


class StatusCodeError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"provider failed with {status_code}")
        self.status_code = status_code


async def test_maps_text_history_tool_result_and_redaction() -> None:
    model = RecordingChatModel(
        AIMessage(
            content="done",
            usage_metadata={"input_tokens": 8, "output_tokens": 2, "total_tokens": 10},
        )
    )
    port = LangChainModelPort(model, redaction_hook=lambda text: text.replace("secret", "X"))

    response = await port.invoke(
        messages=(
            Message(role="system", content="hide secret"),
            Message(role="user", content="hello secret"),
            Message(role="assistant", content="working"),
            ToolResult(id="call_1", content="tool secret is unchanged"),
        )
    )

    sent, kwargs = model.calls[0]
    assert sent == [
        SystemMessage(content="hide X"),
        HumanMessage(content="hello X"),
        AIMessage(content="working"),
        ToolMessage(content="tool secret is unchanged", tool_call_id="call_1"),
    ]
    assert kwargs == {}
    assert response.content == "done"
    assert response.usage == Usage(input_tokens=8, output_tokens=2)


async def test_maps_image_to_provider_neutral_content_block() -> None:
    model = RecordingChatModel()
    port = LangChainModelPort(model)

    await port.invoke(messages=(Message(role="user", content=TINY_PNG),))

    sent = model.calls[0][0]
    assert sent == [
        HumanMessage(
            content_blocks=[{"type": "image", "mime_type": "image/png", "base64": TINY_PNG_DATA}]
        )
    ]


async def test_binds_tools_forwards_temperature_and_maps_response() -> None:
    model = RecordingChatModel(
        AIMessage(
            content=[{"type": "text", "text": "first"}, {"type": "text", "text": "second"}],
            tool_calls=[
                {"id": "call_1", "name": "save", "args": {"value": 1}},
                {"id": "call_2", "name": "notify", "args": {"message": "done"}},
            ],
            usage_metadata={"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
        )
    )
    port = LangChainModelPort(model)
    tool = Tool(
        name="save",
        description="Save a value.",
        parameters_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    )

    response = await port.invoke(
        messages=(Message(role="user", content="save this"),),
        tools=(tool,),
        temperature=0.25,
    )

    assert model.bound_tools == [
        {
            "name": "save",
            "description": "Save a value.",
            "parameters": tool.parameters_schema,
        }
    ]
    assert model.calls[0][1] == {"temperature": 0.25}
    assert response.content == "first\nsecond"
    assert response.tool_calls == (
        ToolCall(id="call_1", name="save", arguments={"value": 1}),
        ToolCall(id="call_2", name="notify", arguments={"message": "done"}),
    )
    assert response.usage == Usage(input_tokens=12, output_tokens=5)


async def test_missing_usage_metadata_defaults_to_zero() -> None:
    port = LangChainModelPort(RecordingChatModel(AIMessage(content="no usage")))

    response = await port.invoke(messages=(Message(role="user", content="hello"),))

    assert response.usage == Usage(input_tokens=0, output_tokens=0)


async def test_invalid_image_data_url_raises_validation_error() -> None:
    model = RecordingChatModel()
    port = LangChainModelPort(model)

    with pytest.raises(ValidationError, match="invalid base64"):
        await port.invoke(messages=(Message(role="user", content="data:image/png;base64,!!!"),))

    assert model.calls == []


async def test_unsupported_message_role_raises_validation_error() -> None:
    port = LangChainModelPort(RecordingChatModel())

    with pytest.raises(ValidationError, match="unsupported model message role"):
        await port.invoke(messages=(Message(role="developer", content="hello"),))


@pytest.mark.parametrize(
    ("exception", "expected_type", "expected_message"),
    [
        (ContextOverflowError("too long"), ValidationError, "model request invalid"),
        (StatusCodeError(400), ValidationError, "model request invalid"),
        (StatusCodeError(401), UnauthorizedError, "model authentication failed"),
        (StatusCodeError(403), ForbiddenError, "model invocation not permitted"),
        (StatusCodeError(429), InternalError, "model rate limit exceeded"),
        (TimeoutError("slow"), InternalError, "model invocation timed out"),
        (ConnectionError("offline"), InternalError, "model invocation connection failed"),
        (StatusCodeError(503), InternalError, "model provider unavailable"),
        (RuntimeError("unexpected"), InternalError, "model invocation failed"),
    ],
)
async def test_translates_model_errors(
    exception: Exception,
    expected_type: type[MangoError],
    expected_message: str,
) -> None:
    port = LangChainModelPort(RecordingChatModel(exception=exception))

    with pytest.raises(expected_type, match=expected_message) as raised:
        await port.invoke(messages=(Message(role="user", content="hello"),))

    assert raised.value.__cause__ is exception


async def test_rejects_tool_call_without_id() -> None:
    model = RecordingChatModel(
        AIMessage(content="", tool_calls=[{"id": None, "name": "save", "args": {}}])
    )
    port = LangChainModelPort(model)

    with pytest.raises(InternalError, match="tool call without an id"):
        await port.invoke(messages=(Message(role="user", content="save"),))
