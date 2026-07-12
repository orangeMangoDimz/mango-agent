"""Unit tests for the agent command registry."""

from __future__ import annotations

import pytest

from mango_agent.agents.contract import Agent, AgentCommandError
from mango_agent.agents.registry import AgentRegistry
from mango_agent.agents.task_management import TaskManagementAgent
from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    NormalizedInboundMessage,
    NormalizedOutboundResponse,
)
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp


class FakeAgent(Agent):
    """A fake agent for testing the registry."""

    def __init__(self, use_cases: dict[str, object]) -> None:
        self._use_cases = use_cases

    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedInboundMessage,
    ) -> NormalizedOutboundResponse:
        return NormalizedOutboundResponse.final_text(f"Fake agent: {payload.text}")


def _make_context() -> AuthenticatedContext:
    return AuthenticatedContext(
        internal_user_id=UserId.generate(),
        bot_id="test-bot",
        command="test-cmd",
        provider=Provider.TELEGRAM,
        provider_user_id="provider-123",
    )


def _make_request(message_text: str = "hello") -> NormalizedInboundMessage:
    return NormalizedInboundMessage(
        provider=Provider.TELEGRAM,
        bot_id="test-bot",
        agent_command="test-cmd",
        provider_event_id="event-123",
        conversation_id="conv-123",
        thread_id=None,
        provider_user_id="provider-123",
        display_name="Test User",
        username="test-user",
        message_id="message-123",
        text=message_text,
        attachments=(),
        reply_to=None,
        received_at=Timestamp.now(),
    )


def test_registry_resolves_task_management_agent() -> None:
    registry = AgentRegistry()
    registry.register("task_management", TaskManagementAgent)

    factory = registry.resolve("task_management")

    assert factory is TaskManagementAgent


def test_registry_rejects_unknown_command() -> None:
    registry = AgentRegistry()
    registry.register("task_management", TaskManagementAgent)

    with pytest.raises(AgentCommandError) as exc_info:
        registry.resolve("unknown_command")

    assert "unknown command" in str(exc_info.value).lower()
    assert "task_management" in str(exc_info.value)


def test_registry_build_returns_agent_instance() -> None:
    registry = AgentRegistry()
    registry.register("fake", FakeAgent)
    registry.register("task_management", TaskManagementAgent)

    agent = registry.build("task_management", {"any": "deps"})
    assert isinstance(agent, TaskManagementAgent)

    fake_agent = registry.build("fake", {"any": "deps"})
    assert isinstance(fake_agent, FakeAgent)


async def test_task_management_agent_execute_returns_acknowledgment() -> None:
    agent = TaskManagementAgent({})
    context = _make_context()
    request = _make_request("create a task")

    response = await agent.execute(context, request)

    assert response.text == "Task management agent received: create a task"
