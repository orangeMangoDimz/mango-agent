"""Agent contract for normalized channel messages and responses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.shared.channel_contracts import (
    NormalizedInboundMessage,
    NormalizedOutboundResponse,
)
from mango_agent.shared.domain.errors import MangoError

__all__ = [
    "Agent",
    "AgentCommandError",
    "AgentResponse",
    "NormalizedRequest",
]

NormalizedRequest = NormalizedInboundMessage
AgentResponse = NormalizedOutboundResponse


@final
class AgentCommandError(MangoError):
    """Raised when the registry is asked to resolve an unknown command."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="agent_command_error")


class Agent(ABC):
    """Common agent interface."""

    @abstractmethod
    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedInboundMessage,
    ) -> NormalizedOutboundResponse:
        """Execute the agent against a normalized request and return a response."""
