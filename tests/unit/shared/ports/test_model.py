from __future__ import annotations

import pytest

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.ports.model import (
    Message,
    ModelPort,
    ModelResponse,
    Tool,
    ToolCall,
    ToolResult,
    Usage,
)


def test_message_requires_non_empty_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="", content="hello")


def test_message_is_frozen() -> None:
    message = Message(role="user", content="hello")
    with pytest.raises(AttributeError):
        message.content = "goodbye"


def test_tool_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        Tool(name="", description="does nothing", parameters_schema={})


def test_tool_requires_dict_parameters_schema() -> None:
    with pytest.raises(ValidationError):
        Tool(name="find", description="finds", parameters_schema=["not a dict"])


def test_tool_call_requires_non_empty_id_and_name() -> None:
    with pytest.raises(ValidationError):
        ToolCall(id="", name="fetch", arguments={})
    with pytest.raises(ValidationError):
        ToolCall(id="call_1", name="", arguments={})


def test_tool_result_requires_non_empty_id() -> None:
    with pytest.raises(ValidationError):
        ToolResult(id="", content="done")


def test_usage_requires_non_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        Usage(input_tokens=-1, output_tokens=0)
    with pytest.raises(ValidationError):
        Usage(input_tokens=0, output_tokens=-1)


def test_model_response_is_frozen() -> None:
    response = ModelResponse(
        content="ok",
        tool_calls=(ToolCall(id="c1", name="save", arguments={}),),
        usage=Usage(input_tokens=5, output_tokens=3),
    )
    with pytest.raises(AttributeError):
        response.content = "changed"


def test_model_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelPort()


async def test_fake_model_port_invoke() -> None:
    class FakeModelPort(ModelPort):
        async def invoke(
            self,
            messages: tuple[Message, ...],
            tools: tuple[Tool, ...] = (),
            temperature: float | None = None,
        ) -> ModelResponse:
            return ModelResponse(
                content="ack",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1),
            )

    port = FakeModelPort()
    response = await port.invoke(
        messages=(Message(role="user", content="hi"),),
        tools=(Tool(name="save", description="save", parameters_schema={}),),
        temperature=0.5,
    )

    assert response.content == "ack"
    assert response.tool_calls == ()
    assert response.usage == Usage(input_tokens=1, output_tokens=1)
