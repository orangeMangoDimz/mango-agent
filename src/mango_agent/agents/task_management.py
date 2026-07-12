"""Task management agent stub."""

from __future__ import annotations

from typing import final

from mango_agent.agents.contract import Agent, AgentResponse, NormalizedRequest
from mango_agent.modules.identity.application.use_cases import AuthenticatedContext

__all__ = ["TaskManagementAgent"]


@final
class TaskManagementAgent(Agent):
    """Agent that handles task-management conversations."""

    def __init__(self, use_cases: dict[str, object]) -> None:
        self._use_cases = use_cases

    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedRequest,
    ) -> AgentResponse:
        return AgentResponse(
            content=f"Task management agent received: {payload.message_text}",
        )
