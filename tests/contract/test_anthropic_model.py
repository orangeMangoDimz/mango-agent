"""Contract tests for AnthropicModelPort."""

from __future__ import annotations

import os

import pytest

from mango_agent.integrations.llm.anthropic_model import AnthropicModelPort
from mango_agent.shared.domain.errors import UnauthorizedError, ValidationError
from mango_agent.shared.ports.model import (
    Message,
    ModelResponse,
    Tool,
    ToolCall,
    ToolResult,
    Usage,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TEST_MODEL = "claude-3-5-haiku-20241022"
TINY_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def live_port() -> AnthropicModelPort:
    if ANTHROPIC_API_KEY is None:
        pytest.skip("ANTHROPIC_API_KEY is not set")
    return AnthropicModelPort(model=TEST_MODEL, api_key=ANTHROPIC_API_KEY)


async def test_simple_text_invocation(live_port: AnthropicModelPort) -> None:
    response = await live_port.invoke(
        messages=(Message(role="user", content="Say hello in exactly one word."),),
    )

    assert response.content is not None
    assert "hello" in response.content.lower()
    assert response.tool_calls == ()
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


async def test_tool_call_invocation(live_port: AnthropicModelPort) -> None:
    response = await live_port.invoke(
        messages=(Message(role="user", content="What is 2 + 2? Use the calculator."),),
        tools=(
            Tool(
                name="calculator",
                description="Evaluate a simple math expression and return the result.",
                parameters_schema={
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            ),
        ),
        temperature=0.0,
    )

    assert response.tool_calls
    call = response.tool_calls[0]
    assert call.name == "calculator"
    assert "expression" in call.arguments
    assert response.usage.output_tokens > 0


async def test_image_input(live_port: AnthropicModelPort) -> None:
    response = await live_port.invoke(
        messages=(Message(role="user", content=TINY_PNG),),
    )

    assert response.content is not None
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


async def test_error_translation() -> None:
    if ANTHROPIC_API_KEY is None:
        pytest.skip("ANTHROPIC_API_KEY is not set")

    port = AnthropicModelPort(model=TEST_MODEL, api_key="invalid-key")
    with pytest.raises(UnauthorizedError):
        await port.invoke(messages=(Message(role="user", content="hi"),))


async def test_fake_mode_without_credentials() -> None:
    expected = ModelResponse(
        content="fake",
        tool_calls=(ToolCall(id="t1", name="save", arguments={"x": 1}),),
        usage=Usage(input_tokens=1, output_tokens=2),
    )
    port = AnthropicModelPort(
        model="claude-test",
        api_key="",
        fake_responses={"hi": expected},
    )

    response = await port.invoke(messages=(Message(role="user", content="hi"),))

    assert response == expected


async def test_fake_mode_with_tool_result() -> None:
    expected = ModelResponse(
        content="ack",
        tool_calls=(),
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    port = AnthropicModelPort(
        model="claude-test",
        api_key="",
        fake_responses=[expected],
    )

    response = await port.invoke(
        messages=(
            Message(role="user", content="use the tool"),
            ToolResult(id="call_1", content="done"),
        ),
    )

    assert response == expected


async def test_redaction_hook_in_fake_mode() -> None:
    expected = ModelResponse(
        content="redacted",
        tool_calls=(),
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    port = AnthropicModelPort(
        model="claude-test",
        api_key="",
        redaction_hook=lambda text: text.replace("secret", "REDACTED"),
        fake_responses={"has REDACTED data": expected},
    )

    response = await port.invoke(messages=(Message(role="user", content="has secret data"),))

    assert response == expected


async def test_invalid_image_data_url_raises_validation_error() -> None:
    port = AnthropicModelPort(
        model="claude-test",
        api_key="",
        fake_responses={"fallback": ModelResponse(content="ok", tool_calls=(), usage=Usage(0, 0))},
    )

    with pytest.raises(ValidationError):
        await port.invoke(messages=(Message(role="user", content="data:image/png;base64,!!!"),))


async def test_empty_model_name_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        AnthropicModelPort(model="", api_key="sk-test")


async def test_empty_api_key_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        AnthropicModelPort(model="claude-test", api_key="")
