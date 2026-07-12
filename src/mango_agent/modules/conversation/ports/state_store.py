"""Conversation-state ports.

These ports abstract the storage of short-lived, command-scoped conversation
state. Implementations are expected to use an expiring key/value store (e.g.
Redis). Expiration semantics are part of the contract:

- Conversation state: 24 hours.
- Pending proposals: 2 hours.
- Pending confirmations: 2 hours.
- Temporary attachment references kept inside conversation state: 24 hours,
  matching the conversation-state TTL.

All writes use optimistic concurrency: each load returns a monotonic version,
and save/consume operations only succeed when the provided expected version
matches the current stored version.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from mango_agent.modules.conversation.domain import (
    ConversationState,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import OperationId, UserId


@final
@dataclass(frozen=True, slots=True)
class ConversationKey:
    """Scoped key for a single conversation state entry.

    The key encodes the provider, bot instance, provider-side conversation
    identifier, optional provider-side thread identifier, internal user, and
    agent command so that state is never shared across users, bots, threads,
    or commands.
    """

    provider: Provider
    bot_id: str
    conversation_id: str
    user_id: UserId
    command: str
    thread_id: str | None = None

    def __post_init__(self) -> None:
        if not self.bot_id.strip():
            raise ValidationError("bot id must not be empty")
        if not self.conversation_id.strip():
            raise ValidationError("conversation id must not be empty")
        if not self.command.strip():
            raise ValidationError("command must not be empty")
        if self.thread_id is not None:
            if not isinstance(self.thread_id, str) or not self.thread_id.strip():
                raise ValidationError("thread_id must be a non-empty string or None")
            object.__setattr__(self, "thread_id", self.thread_id.strip())
        if not isinstance(self.provider, Provider):
            raise ValidationError("provider must be a Provider value")
        if not isinstance(self.user_id, UserId):
            raise ValidationError("user_id must be a UserId")

    def __str__(self) -> str:
        thread_scope = (
            "no-thread"
            if self.thread_id is None
            else f"thread-{len(self.thread_id)}-{self.thread_id}"
        )
        return (
            f"conversation:{self.provider.value}:"
            f"{self.bot_id}:{self.conversation_id}:{thread_scope}:"
            f"{self.user_id}:{self.command}"
        )


class ConversationStateStore(ABC):
    """Port for loading and saving expiring conversation state.

    Implementations must store state with a 24-hour TTL.
    """

    @abstractmethod
    async def load(self, key: ConversationKey) -> tuple[ConversationState, int] | None:
        """Return the current state and its version, or None if not found."""

    @abstractmethod
    async def save(
        self, key: ConversationKey, state: ConversationState, expected_version: int
    ) -> bool:
        """Persist state only if the current version matches expected_version.

        Returns True on success, False on stale version.
        """

    @abstractmethod
    async def clear(self, key: ConversationKey) -> None:
        """Remove the state entry for the key."""


class ProposalStore(ABC):
    """Port for creating, reading, and atomically consuming pending proposals.

    Proposals expire after 2 hours. The ``consume`` operation marks a proposal
    as consumed only when the operation id and stored version match, preventing
    duplicate approvals.
    """

    @abstractmethod
    async def create(self, key: ConversationKey, proposal: PendingProposal) -> int:
        """Store a new proposal and return its initial version."""

    @abstractmethod
    async def get(self, key: ConversationKey) -> tuple[PendingProposal, int] | None:
        """Return the active proposal and its version, or None if not found."""

    @abstractmethod
    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        """Mark the proposal consumed only if its version matches.

        Returns True on success, False on stale version or missing operation.
        """

    @abstractmethod
    async def clear(self, key: ConversationKey) -> None:
        """Remove the proposal for the key."""


class ConfirmationStore(ABC):
    """Port for creating, reading, and atomically consuming pending confirmations.

    Confirmations expire after 2 hours. The ``consume`` operation marks a
    confirmation as consumed only when the operation id and stored version match,
    preventing duplicate confirmations.
    """

    @abstractmethod
    async def create(self, key: ConversationKey, confirmation: PendingConfirmation) -> int:
        """Store a new confirmation and return its initial version."""

    @abstractmethod
    async def get(self, key: ConversationKey) -> tuple[PendingConfirmation, int] | None:
        """Return the active confirmation and its version, or None if not found."""

    @abstractmethod
    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        """Mark the confirmation consumed only if its version matches.

        Returns True on success, False on stale version or missing operation.
        """

    @abstractmethod
    async def clear(self, key: ConversationKey) -> None:
        """Remove the confirmation for the key."""
