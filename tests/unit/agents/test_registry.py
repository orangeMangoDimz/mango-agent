"""Unit tests for the agent command registry."""

from __future__ import annotations

import pytest

from mango_agent.agents.contract import (
    Agent,
    AgentCommandError,
    AgentResponse,
    NormalizedRequest,
)
from mango_agent.agents.registry import AgentRegistry
from mango_agent.agents.task_management import TaskManagementAgent
from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import UserId


class FakeAgent(Agent):
    """A fake agent for testing the registry."""

    def __init__(self, use_cases: dict[str, object]) -> None:
        self._use_cases = use_cases

    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedRequest,
    ) -> AgentResponse:
        return AgentResponse(content=f"Fake agent: {payload.message_text}")


def _make_context() -> AuthenticatedContext:
    return AuthenticatedContext(
        internal_user_id=UserId.generate(),
        bot_id="test-bot",
        command="test-cmd",
        provider=Provider.TELEGRAM,
        provider_user_id="provider-123",
    )


def _make_request(message_text: str | None = "hello") -> NormalizedRequest:
    return NormalizedRequest(
        provider=Provider.TELEGRAM,
        bot_id="test-bot",
        conversation_id="conv-123",
        provider_user_id="provider-123",
        message_text=message_text,
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

    assert response.content == "Task management agent received: create a task"
    assert response.action is None
