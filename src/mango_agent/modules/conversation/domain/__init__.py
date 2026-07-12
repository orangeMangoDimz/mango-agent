"""Conversation domain model."""

from __future__ import annotations

from mango_agent.modules.conversation.domain.confirmation import PendingConfirmation
from mango_agent.modules.conversation.domain.enums import MessageRole
from mango_agent.modules.conversation.domain.proposal import PendingProposal
from mango_agent.modules.conversation.domain.state import (
    Approval,
    ConversationState,
    Message,
    Participant,
)

__all__ = [
    "Approval",
    "ConversationState",
    "Message",
    "MessageRole",
    "Participant",
    "PendingConfirmation",
    "PendingProposal",
]
