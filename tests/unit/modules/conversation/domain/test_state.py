from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mango_agent.modules.conversation.domain import (
    ConversationState,
    Message,
    MessageRole,
    Participant,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, OperationId, ProjectId, TaskId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


def _future(seconds: int = 60) -> Timestamp:
    return Timestamp.from_datetime(datetime.now(tz=UTC) + timedelta(seconds=seconds))


def _participant(user_id: UserId | None = None) -> Participant:
    return Participant(
        user_id=user_id or UserId.generate(),
        provider=Provider.TELEGRAM,
        provider_user_id="12345",
    )


def _state(user_id: UserId | None = None) -> ConversationState:
    return ConversationState.create(_participant(user_id), "bot-1")


def test_state_create() -> None:
    state = _state()
    assert state.bot_id == "bot-1"
    assert state.messages == ()
    assert state.pending_proposal is None
    assert state.pending_confirmation is None


def test_state_empty_bot_id_raises() -> None:
    with pytest.raises(ValidationError):
        ConversationState.create(_participant(), "   ")


def test_state_record_message_bounds_history() -> None:
    state = _state()
    for i in range(60):
        state = state.record_message(
            Message(role=MessageRole.USER, content=f"msg {i}", timestamp=Timestamp.now())
        )
    assert len(state.messages) == 50
    assert state.messages[0].content == "msg 10"


def test_state_set_last_project_and_task() -> None:
    state = _state()
    project_id = ProjectId.generate()
    task_id = TaskId.generate()
    state = state.set_last_project(project_id).set_last_task(task_id)
    assert state.last_project_id == project_id
    assert state.last_task_id == task_id


def test_state_set_temp_attachments() -> None:
    state = _state()
    attachment_id = AttachmentId.generate()
    state = state.set_temp_attachments((attachment_id,))
    assert state.temp_attachment_ids == (attachment_id,)


def test_state_approve_proposal_success() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future())
    state = state.set_proposal(proposal)

    result = state.approve_proposal(user_id, operation_id, Timestamp.now())
    assert result.is_success
    approval, new_state = result.value
    assert approval.operation_id == operation_id
    assert approval.proposal_version == 1
    assert new_state.pending_proposal is not None
    assert new_state.pending_proposal.consumed is True


def test_state_approve_proposal_expired_fails() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future(1))
    state = state.set_proposal(proposal)

    result = state.approve_proposal(user_id, operation_id, _future(2))
    assert result.is_failure
    assert result.error.code == "conflict"


def test_state_approve_proposal_wrong_user_fails() -> None:
    owner = UserId.generate()
    other = UserId.generate()
    state = _state(owner)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future())
    state = state.set_proposal(proposal)

    result = state.approve_proposal(other, operation_id, Timestamp.now())
    assert result.is_failure
    assert result.error.code == "forbidden"


def test_state_approve_proposal_wrong_operation_fails() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    proposal = PendingProposal.create(OperationId.generate(), "Create task", expires_at=_future())
    state = state.set_proposal(proposal)

    result = state.approve_proposal(user_id, OperationId.generate(), Timestamp.now())
    assert result.is_failure
    assert result.error.code == "conflict"


def test_state_approve_proposal_already_consumed_fails() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future())
    state = state.set_proposal(proposal)
    approved, _ = state.approve_proposal(user_id, operation_id, Timestamp.now()).value

    result = state.set_proposal(state.pending_proposal.consume()).approve_proposal(
        user_id, operation_id, Timestamp.now()
    )
    assert result.is_failure
    assert result.error.code == "conflict"


def test_state_approve_confirmation_success() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    confirmation = PendingConfirmation.create(
        operation_id, "delete_task", "task-123", expires_at=_future()
    )
    state = state.set_confirmation(confirmation)

    result = state.approve_confirmation(user_id, operation_id, Timestamp.now())
    assert result.is_success
    approval, new_state = result.value
    assert approval.confirmation_type == "delete_task"
    assert new_state.pending_confirmation is not None
    assert new_state.pending_confirmation.consumed is True


def test_state_is_approval_valid_true_for_matching_proposal() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future())
    state = state.set_proposal(proposal)
    approval, state = state.approve_proposal(user_id, operation_id, Timestamp.now()).value

    assert state.is_approval_valid(approval, Timestamp.now()) is True


def test_state_is_approval_valid_false_after_revision() -> None:
    user_id = UserId.generate()
    state = _state(user_id)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task", expires_at=_future())
    state = state.set_proposal(proposal)
    approval, state = state.approve_proposal(user_id, operation_id, Timestamp.now()).value

    revised = proposal.revise("Create task updated", expires_at=_future(120))
    state = state.set_proposal(revised)

    assert state.is_approval_valid(approval, Timestamp.now()) is False
