"""Task management agent stub."""

from __future__ import annotations

from typing import final

from mango_agent.agents.contract import Agent, NormalizedRequest
from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.shared.channel_contracts import NormalizedOutboundResponse

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
    ) -> NormalizedOutboundResponse:
        return NormalizedOutboundResponse.final_text(
            f"Task management agent received: {payload.message_text}",
        )
