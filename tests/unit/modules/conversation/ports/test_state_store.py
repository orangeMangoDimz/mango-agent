from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mango_agent.modules.conversation.domain import (
    ConversationState,
    Participant,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.conversation.ports import (
    ConfirmationStore,
    ConversationKey,
    ConversationStateStore,
    ProposalStore,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import OperationId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


def _participant() -> Participant:
    return Participant(
        user_id=UserId.generate(),
        provider=Provider.TELEGRAM,
        provider_user_id="12345",
    )


def _key(
    bot_id: str = "bot-1",
    conversation_id: str = "thread-1",
    command: str = "task_management",
) -> ConversationKey:
    return ConversationKey(
        provider=Provider.TELEGRAM,
        bot_id=bot_id,
        conversation_id=conversation_id,
        user_id=UserId.generate(),
        command=command,
    )


def _future(seconds: int = 60) -> Timestamp:
    return Timestamp.from_datetime(datetime.now(tz=UTC) + timedelta(seconds=seconds))


def test_conversation_key_create() -> None:
    key = _key()
    assert key.provider == Provider.TELEGRAM
    assert key.bot_id == "bot-1"
    assert key.conversation_id == "thread-1"
    assert key.command == "task_management"
    assert str(key).startswith("conversation:telegram:bot-1:thread-1:")


def test_conversation_key_empty_bot_id_raises() -> None:
    with pytest.raises(ValidationError):
        _key(bot_id="   ")


def test_conversation_key_empty_conversation_id_raises() -> None:
    with pytest.raises(ValidationError):
        _key(conversation_id="   ")


def test_conversation_key_empty_command_raises() -> None:
    with pytest.raises(ValidationError):
        _key(command="   ")


def test_conversation_key_invalid_provider_raises() -> None:
    with pytest.raises(ValidationError):
        ConversationKey(
            provider="telegram",  # type: ignore[arg-type]
            bot_id="bot-1",
            conversation_id="thread-1",
            user_id=UserId.generate(),
            command="task_management",
        )


def test_conversation_key_invalid_user_id_raises() -> None:
    with pytest.raises(ValidationError):
        ConversationKey(
            provider=Provider.TELEGRAM,
            bot_id="bot-1",
            conversation_id="thread-1",
            user_id="not-a-user-id",  # type: ignore[arg-type]
            command="task_management",
        )


def test_conversation_state_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        ConversationStateStore()


def test_proposal_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        ProposalStore()


def test_confirmation_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        ConfirmationStore()


def test_conversation_state_store_requires_all_methods() -> None:
    class Partial(ConversationStateStore):
        async def load(self, key: ConversationKey) -> None:
            return None

    with pytest.raises(TypeError):
        Partial()


def test_proposal_store_requires_all_methods() -> None:
    class Partial(ProposalStore):
        async def create(self, key: ConversationKey, proposal: PendingProposal) -> int:
            return 1

    with pytest.raises(TypeError):
        Partial()


def test_confirmation_store_requires_all_methods() -> None:
    class Partial(ConfirmationStore):
        async def create(self, key: ConversationKey, confirmation: PendingConfirmation) -> int:
            return 1

    with pytest.raises(TypeError):
        Partial()


async def test_conversation_state_store_fake_implements_contract() -> None:
    class Fake(ConversationStateStore):
        async def load(self, key: ConversationKey) -> tuple[ConversationState, int] | None:
            return None

        async def save(
            self, key: ConversationKey, state: ConversationState, expected_version: int
        ) -> bool:
            return True

        async def clear(self, key: ConversationKey) -> None:
            return None

    store = Fake()
    result = await store.load(_key())
    assert result is None
    assert await store.save(_key(), ConversationState.create(_participant(), "bot-1"), 0) is True


async def test_proposal_store_fake_implements_contract() -> None:
    class Fake(ProposalStore):
        async def create(self, key: ConversationKey, proposal: PendingProposal) -> int:
            return 1

        async def get(self, key: ConversationKey) -> tuple[PendingProposal, int] | None:
            return None

        async def consume(
            self, key: ConversationKey, operation_id: OperationId, expected_version: int
        ) -> bool:
            return True

        async def clear(self, key: ConversationKey) -> None:
            return None

    store = Fake()
    proposal = PendingProposal.create(OperationId.generate(), "Do it", expires_at=_future())
    assert await store.create(_key(), proposal) == 1
    assert await store.get(_key()) is None
    assert await store.consume(_key(), OperationId.generate(), 1) is True


async def test_confirmation_store_fake_implements_contract() -> None:
    class Fake(ConfirmationStore):
        async def create(self, key: ConversationKey, confirmation: PendingConfirmation) -> int:
            return 1

        async def get(self, key: ConversationKey) -> tuple[PendingConfirmation, int] | None:
            return None

        async def consume(
            self, key: ConversationKey, operation_id: OperationId, expected_version: int
        ) -> bool:
            return True

        async def clear(self, key: ConversationKey) -> None:
            return None

    store = Fake()
    confirmation = PendingConfirmation.create(
        OperationId.generate(), "delete_task", "task-123", expires_at=_future()
    )
    assert await store.create(_key(), confirmation) == 1
    assert await store.get(_key()) is None
    assert await store.consume(_key(), OperationId.generate(), 1) is True
