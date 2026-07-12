"""Fakes for conversation-state unit tests."""

from __future__ import annotations

from mango_agent.modules.conversation.domain import (
    ConversationState,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.conversation.ports.state_store import (
    ConfirmationStore,
    ConversationKey,
    ConversationStateStore,
    ProposalStore,
)
from mango_agent.shared.domain.ids import OperationId


class FakeConversationStateStore(ConversationStateStore):
    def __init__(self) -> None:
        self._states: dict[ConversationKey, tuple[ConversationState, int]] = {}

    async def load(self, key: ConversationKey) -> tuple[ConversationState, int] | None:
        return self._states.get(key)

    async def save(
        self, key: ConversationKey, state: ConversationState, expected_version: int
    ) -> bool:
        current = self._states.get(key)
        if current is None:
            if expected_version != 0:
                return False
            self._states[key] = (state, 1)
            return True

        _state, version = current
        if version != expected_version:
            return False
        self._states[key] = (state, version + 1)
        return True

    async def clear(self, key: ConversationKey) -> None:
        self._states.pop(key, None)


class FakeProposalStore(ProposalStore):
    def __init__(self) -> None:
        self._proposals: dict[ConversationKey, tuple[PendingProposal, int]] = {}

    async def create(self, key: ConversationKey, proposal: PendingProposal) -> int:
        self._proposals[key] = (proposal, proposal.version)
        return proposal.version

    async def get(self, key: ConversationKey) -> tuple[PendingProposal, int] | None:
        return self._proposals.get(key)

    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        stored = self._proposals.get(key)
        if stored is None:
            return False
        proposal, version = stored
        if version != expected_version or proposal.operation_id != operation_id:
            return False
        consumed = proposal.consume()
        self._proposals[key] = (consumed, version + 1)
        return True

    async def clear(self, key: ConversationKey) -> None:
        self._proposals.pop(key, None)


class FakeConfirmationStore(ConfirmationStore):
    def __init__(self) -> None:
        self._confirmations: dict[ConversationKey, tuple[PendingConfirmation, int]] = {}

    async def create(self, key: ConversationKey, confirmation: PendingConfirmation) -> int:
        self._confirmations[key] = (confirmation, 1)
        return 1

    async def get(self, key: ConversationKey) -> tuple[PendingConfirmation, int] | None:
        return self._confirmations.get(key)

    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        stored = self._confirmations.get(key)
        if stored is None:
            return False
        confirmation, version = stored
        if version != expected_version or confirmation.operation_id != operation_id:
            return False
        consumed = confirmation.consume()
        self._confirmations[key] = (consumed, version + 1)
        return True

    async def clear(self, key: ConversationKey) -> None:
        self._confirmations.pop(key, None)
