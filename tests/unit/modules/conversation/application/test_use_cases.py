"""Tests for conversation workflow application use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mango_agent.modules.conversation.application.use_cases import (
    ClearCompletedOrRejectedState,
    ConsumeConfirmation,
    ConsumeProposalApproval,
    CreatePendingConfirmation,
    CreatePendingProposal,
    LoadScopedState,
    ReviseProposal,
    SaveScopedState,
)
from mango_agent.modules.conversation.domain import (
    ConversationState,
    Participant,
)
from mango_agent.modules.conversation.ports import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import AttachmentId, OperationId, UserId
from mango_agent.shared.domain.value_objects import Timestamp

from ..fakes import (
    FakeConfirmationStore,
    FakeConversationStateStore,
    FakeProposalStore,
)


def _participant(user_id: UserId | None = None) -> Participant:
    return Participant(
        user_id=user_id or UserId.generate(),
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


async def test_load_and_save_state_with_version() -> None:
    state_store = FakeConversationStateStore()
    load_state = LoadScopedState(state_store)
    save_state = SaveScopedState(state_store)
    key = _key()
    state = ConversationState.create(_participant(key.user_id), key.bot_id)

    assert (await load_state(key)).value is None

    saved = await save_state(key, state, 0)
    assert saved.is_success
    assert saved.value is True

    loaded = await load_state(key)
    assert loaded.is_success
    assert loaded.value is not None
    loaded_state, version = loaded.value
    assert loaded_state == state
    assert version == 1

    stale = await save_state(key, state, 0)
    assert stale.is_failure
    assert stale.error.code == "conflict"


async def test_create_and_consume_proposal() -> None:
    proposal_store = FakeProposalStore()
    create_proposal = CreatePendingProposal(proposal_store)
    consume_proposal = ConsumeProposalApproval(proposal_store)
    key = _key()
    operation_id = OperationId.generate()

    created = await create_proposal(
        key, operation_id, "Create task", (AttachmentId.generate(),), _future()
    )
    assert created.is_success
    assert created.value == 1

    consumed = await consume_proposal(key, operation_id, 1, Timestamp.now())
    assert consumed.is_success
    approval = consumed.value
    assert approval.operation_id == operation_id
    assert approval.user_id == key.user_id
    assert approval.scope == str(key)
    assert approval.proposal_version == 1
    assert approval.confirmation_type is None


async def test_revise_proposal_invalidates_prior_approval() -> None:
    proposal_store = FakeProposalStore()
    create_proposal = CreatePendingProposal(proposal_store)
    consume_proposal = ConsumeProposalApproval(proposal_store)
    revise_proposal = ReviseProposal(proposal_store)
    key = _key()
    operation_id = OperationId.generate()

    await create_proposal(key, operation_id, "v1", (), _future())
    first_approval = await consume_proposal(key, operation_id, 1, Timestamp.now())
    assert first_approval.is_success

    revised = await revise_proposal(key, "v2", (), _future())
    assert revised.is_success
    assert revised.value == 2

    stale = await consume_proposal(key, operation_id, 1, Timestamp.now())
    assert stale.is_failure
    assert stale.error.code == "conflict"

    fresh = await consume_proposal(key, operation_id, 2, Timestamp.now())
    assert fresh.is_success
    assert fresh.value.proposal_version == 2


async def test_create_and_consume_confirmation() -> None:
    confirmation_store = FakeConfirmationStore()
    create_confirmation = CreatePendingConfirmation(confirmation_store)
    consume_confirmation = ConsumeConfirmation(confirmation_store)
    key = _key()
    operation_id = OperationId.generate()

    created = await create_confirmation(
        key, operation_id, "delete_task", "task-123", _future()
    )
    assert created.is_success
    assert created.value == 1

    consumed = await consume_confirmation(key, operation_id, 1, Timestamp.now())
    assert consumed.is_success
    approval = consumed.value
    assert approval.operation_id == operation_id
    assert approval.user_id == key.user_id
    assert approval.confirmation_type == "delete_task"
    assert approval.proposal_version is None


async def test_expired_proposal_refuses_approval() -> None:
    proposal_store = FakeProposalStore()
    create_proposal = CreatePendingProposal(proposal_store)
    consume_proposal = ConsumeProposalApproval(proposal_store)
    key = _key()
    operation_id = OperationId.generate()

    await create_proposal(key, operation_id, "Do it", (), _future(1))
    result = await consume_proposal(key, operation_id, 1, _future(2))
    assert result.is_failure
    assert result.error.code == "conflict"
    assert "expired" in result.error.message


async def test_clear_completed_or_rejected_state() -> None:
    state_store = FakeConversationStateStore()
    proposal_store = FakeProposalStore()
    confirmation_store = FakeConfirmationStore()
    load_state = LoadScopedState(state_store)
    save_state = SaveScopedState(state_store)
    create_proposal = CreatePendingProposal(proposal_store)
    create_confirmation = CreatePendingConfirmation(confirmation_store)
    clear_state = ClearCompletedOrRejectedState(
        state_store, proposal_store, confirmation_store
    )
    key = _key()
    state = ConversationState.create(_participant(key.user_id), key.bot_id)

    await save_state(key, state, 0)
    await create_proposal(key, OperationId.generate(), "Do it", (), _future())
    await create_confirmation(
        key, OperationId.generate(), "delete_project", "project-1", _future()
    )

    cleared = await clear_state(key)
    assert cleared.is_success

    assert (await load_state(key)).value is None
    assert await proposal_store.get(key) is None
    assert await confirmation_store.get(key) is None


async def test_atomic_single_use_consume_fails_on_duplicate() -> None:
    proposal_store = FakeProposalStore()
    create_proposal = CreatePendingProposal(proposal_store)
    consume_proposal = ConsumeProposalApproval(proposal_store)
    key = _key()
    operation_id = OperationId.generate()

    await create_proposal(key, operation_id, "Do it", (), _future())
    first = await consume_proposal(key, operation_id, 1, Timestamp.now())
    assert first.is_success

    second = await consume_proposal(key, operation_id, 1, Timestamp.now())
    assert second.is_failure
    assert second.error.code == "conflict"


async def test_consume_proposal_wrong_operation_fails() -> None:
    proposal_store = FakeProposalStore()
    create_proposal = CreatePendingProposal(proposal_store)
    consume_proposal = ConsumeProposalApproval(proposal_store)
    key = _key()
    operation_id = OperationId.generate()

    await create_proposal(key, operation_id, "Do it", (), _future())
    result = await consume_proposal(key, OperationId.generate(), 1, Timestamp.now())
    assert result.is_failure
    assert result.error.code == "conflict"
