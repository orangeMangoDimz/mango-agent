"""Agent contract for normalized inbound requests and provider-independent responses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import final

from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import MangoError
from mango_agent.shared.domain.ids import AttachmentId

__all__ = [
    "Agent",
    "AgentAction",
    "AgentCommandError",
    "AgentResponse",
    "AttachmentRef",
    "NormalizedRequest",
    "ProposeAction",
    "ReplyAction",
]


@final
@dataclass(frozen=True, slots=True)
class AttachmentRef:
    """Reference to an attachment received in a normalized inbound request."""

    attachment_id: AttachmentId
    original_filename: str
    mime_type: str
    object_key: str


@final
@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    """Provider-independent inbound message."""

    provider: Provider
    bot_id: str
    conversation_id: str
    provider_user_id: str
    message_text: str | None = None
    attachments: tuple[AttachmentRef, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@final
@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Provider-independent response from an agent."""

    content: str | None = None
    action: AgentAction | None = None


@dataclass(frozen=True, slots=True)
class AgentAction:
    """Base class for provider-independent actions emitted by an agent."""


@final
@dataclass(frozen=True, slots=True)
class ReplyAction(AgentAction):
    """A simple text reply action."""

    text: str


@final
@dataclass(frozen=True, slots=True)
class ProposeAction(AgentAction):
    """A proposal action that requires explicit approval."""

    proposal_id: str
    text: str


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
        payload: NormalizedRequest,
    ) -> AgentResponse:
        """Execute the agent against a normalized request and return a response."""
