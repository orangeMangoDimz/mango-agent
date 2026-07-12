"""Integration tests for the LangSmith tracing adapter."""

from __future__ import annotations

import os
import uuid
from types import MappingProxyType

import pytest
from pydantic import SecretStr

from mango_agent.integrations.llm.langsmith_tracing import LangSmithTracingPort
from mango_agent.shared.infrastructure import correlation
from mango_agent.shared.ports.tracing import (
    RedactionCategory,
    RedactionPolicy,
    SpanId,
)


@pytest.fixture
def disabled_port() -> LangSmithTracingPort:
    return LangSmithTracingPort(api_key=None, project_name=None, enabled=False)


@pytest.fixture
def real_port() -> LangSmithTracingPort:
    if os.environ.get("LANGSMITH_ENABLED", "").lower() != "true":
        pytest.skip("LANGSMITH_ENABLED is not true")
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        pytest.skip("LANGSMITH_API_KEY is not set")
    project_name = os.environ.get("LANGSMITH_PROJECT", "mango-agent-tests")
    return LangSmithTracingPort(
        api_key=SecretStr(api_key),
        project_name=project_name,
        enabled=True,
    )


async def test_start_and_end_span(disabled_port: LangSmithTracingPort) -> None:
    span = await disabled_port.start_span("test-span")
    assert span.name == "test-span"
    assert isinstance(span.id, SpanId)
    assert span.correlation_id is None

    await disabled_port.end_span(span.id)
    state = disabled_port._spans[span.id]
    assert "duration_ms" in state.attributes
    assert isinstance(state.attributes["duration_ms"], int)


async def test_set_attributes(disabled_port: LangSmithTracingPort) -> None:
    span = await disabled_port.start_span("attribute-span")
    await disabled_port.set_attribute(span.id, "agent_command", "create_task")
    await disabled_port.set_attribute(span.id, "tool_name", "task_creation")
    await disabled_port.set_attribute(span.id, "operation_type", "command")
    await disabled_port.set_attribute(span.id, "outcome", "success")

    state = disabled_port._spans[span.id]
    assert state.attributes["agent_command"] == "create_task"
    assert state.attributes["tool_name"] == "task_creation"
    assert state.attributes["operation_type"] == "command"
    assert state.attributes["outcome"] == "success"


async def test_redaction_policy(disabled_port: LangSmithTracingPort) -> None:
    policy = RedactionPolicy(
        hooks=MappingProxyType(
            {
                RedactionCategory.FULL_TEXT: lambda value: "[REDACTED]",
                RedactionCategory.CREDENTIALS: lambda value: "[CREDENTIALS]",
                RedactionCategory.OBJECT_URL: lambda value: "[URL]",
                RedactionCategory.NOTES: lambda value: "[NOTE]",
                RedactionCategory.IMAGE_DERIVED_TEXT: lambda value: "[IMAGE]",
            }
        )
    )
    span = await disabled_port.start_span("redaction-span")

    await disabled_port.set_attribute(span.id, "full_text", "secret message", redaction=policy)
    await disabled_port.set_attribute(span.id, "credentials", "password123", redaction=policy)
    await disabled_port.set_attribute(
        span.id, "object_url", "https://r2.example.com/file", redaction=policy
    )
    await disabled_port.set_attribute(span.id, "notes", "sensitive note", redaction=policy)
    await disabled_port.set_attribute(span.id, "image_derived_text", "image text", redaction=policy)
    await disabled_port.set_attribute(span.id, "agent_command", "create_task", redaction=policy)

    state = disabled_port._spans[span.id]
    assert state.attributes["full_text"] == "[REDACTED]"
    assert state.attributes["credentials"] == "[CREDENTIALS]"
    assert state.attributes["object_url"] == "[URL]"
    assert state.attributes["notes"] == "[NOTE]"
    assert state.attributes["image_derived_text"] == "[IMAGE]"
    assert state.attributes["agent_command"] == "create_task"


async def test_correlation_id_propagation(
    disabled_port: LangSmithTracingPort,
) -> None:
    explicit_id = uuid.uuid4()
    correlation.set_correlation_id(explicit_id)

    span = await disabled_port.start_span("correlation-span")
    assert span.correlation_id == explicit_id

    new_id = uuid.uuid4()
    await disabled_port.set_correlation_id(new_id)
    span2 = await disabled_port.start_span("correlation-span-2")
    assert span2.correlation_id == new_id


async def test_disabled_mode_does_not_fail(
    disabled_port: LangSmithTracingPort,
) -> None:
    span = await disabled_port.start_span("noop-span")
    await disabled_port.set_attribute(span.id, "operation_type", "noop")
    await disabled_port.end_span(span.id)
    assert span.id in disabled_port._spans


async def test_nested_parent_child_spans(
    disabled_port: LangSmithTracingPort,
) -> None:
    parent = await disabled_port.start_span("parent")
    child = await disabled_port.start_span("child", parent_id=parent.id)
    grandchild = await disabled_port.start_span("grandchild", parent_id=child.id)

    assert disabled_port._spans[child.id].parent_id == parent.id
    assert disabled_port._spans[grandchild.id].parent_id == child.id

    await disabled_port.end_span(grandchild.id)
    await disabled_port.end_span(child.id)
    await disabled_port.end_span(parent.id)


async def test_real_langsmith_span_lifecycle(real_port: LangSmithTracingPort) -> None:
    correlation_id = uuid.uuid4()
    await real_port.set_correlation_id(correlation_id)
    span = await real_port.start_span("integration-span")

    await real_port.set_attribute(span.id, "agent_command", "integration_test")
    await real_port.set_attribute(span.id, "tool_name", "langsmith")
    await real_port.set_attribute(span.id, "operation_type", "test")
    await real_port.set_attribute(span.id, "outcome", "success")

    await real_port.end_span(span.id)
    assert span.correlation_id == correlation_id
