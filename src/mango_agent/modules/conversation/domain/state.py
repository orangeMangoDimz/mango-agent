"""Conversation state and approval value objects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.conversation.domain.confirmation import PendingConfirmation
from mango_agent.modules.conversation.domain.enums import MessageRole
from mango_agent.modules.conversation.domain.proposal import PendingProposal
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    MangoError,
    ValidationError,
)
from mango_agent.shared.domain.ids import AttachmentId, OperationId, ProjectId, TaskId, UserId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import Timestamp

MAX_RECENT_MESSAGES = 50


@final
@dataclass(frozen=True, slots=True)
class Participant:
    user_id: UserId
    provider: Provider
    provider_user_id: str

    def __post_init__(self) -> None:
        if not self.provider_user_id.strip():
            raise ValidationError("provider user id must not be empty")
        if not isinstance(self.provider, Provider):
            raise ValidationError("provider must be a Provider value")


@final
@dataclass(frozen=True, slots=True)
class Message:
    role: MessageRole
    content: str
    timestamp: Timestamp

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValidationError("message content must not be empty")
        if not isinstance(self.role, MessageRole):
            raise ValidationError("role must be a MessageRole value")


@final
@dataclass(frozen=True, slots=True)
class Approval:
    operation_id: OperationId
    user_id: UserId
    scope: str
    proposal_version: int | None
    confirmation_type: str | None
    approved_at: Timestamp


@final
@dataclass(frozen=True, slots=True)
class ConversationState:
    participant: Participant
    bot_id: str
    messages: tuple[Message, ...]
    last_project_id: ProjectId | None
    last_task_id: TaskId | None
    temp_attachment_ids: tuple[AttachmentId, ...]
    checkpoint_ref: str | None
    pending_proposal: PendingProposal | None
    pending_confirmation: PendingConfirmation | None
    created_at: Timestamp
    updated_at: Timestamp

    @classmethod
    def create(cls, participant: Participant, bot_id: str) -> ConversationState:
        if not bot_id.strip():
            raise ValidationError("bot id must not be empty")
        now = Timestamp.now()
        return cls(
            participant=participant,
            bot_id=bot_id.strip(),
            messages=(),
            last_project_id=None,
            last_task_id=None,
            temp_attachment_ids=(),
            checkpoint_ref=None,
            pending_proposal=None,
            pending_confirmation=None,
            created_at=now,
            updated_at=now,
        )

    def record_message(self, message: Message) -> ConversationState:
        messages = self.messages + (message,)
        if len(messages) > MAX_RECENT_MESSAGES:
            messages = messages[-MAX_RECENT_MESSAGES:]
        return replace(self, messages=messages, updated_at=Timestamp.now())

    def set_last_project(self, project_id: ProjectId | None) -> ConversationState:
        return replace(self, last_project_id=project_id, updated_at=Timestamp.now())

    def set_last_task(self, task_id: TaskId | None) -> ConversationState:
        return replace(self, last_task_id=task_id, updated_at=Timestamp.now())

    def set_temp_attachments(self, attachment_ids: tuple[AttachmentId, ...]) -> ConversationState:
        return replace(self, temp_attachment_ids=attachment_ids, updated_at=Timestamp.now())

    def set_checkpoint_ref(self, checkpoint_ref: str | None) -> ConversationState:
        return replace(self, checkpoint_ref=checkpoint_ref, updated_at=Timestamp.now())

    def set_proposal(self, proposal: PendingProposal | None) -> ConversationState:
        return replace(self, pending_proposal=proposal, updated_at=Timestamp.now())

    def set_confirmation(self, confirmation: PendingConfirmation | None) -> ConversationState:
        return replace(self, pending_confirmation=confirmation, updated_at=Timestamp.now())

    def approve_proposal(
        self, user_id: UserId, operation_id: OperationId, approved_at: Timestamp
    ) -> Result[tuple[Approval, ConversationState], MangoError]:
        if self.pending_proposal is None:
            return Result.failure(ConflictError("no pending proposal"))
        proposal = self.pending_proposal
        if proposal.operation_id != operation_id:
            return Result.failure(ConflictError("operation id does not match active proposal"))
        if proposal.consumed:
            return Result.failure(ConflictError("proposal already consumed"))
        if proposal.is_expired(approved_at):
            return Result.failure(ConflictError("proposal has expired"))
        if self.participant.user_id != user_id:
            return Result.failure(ForbiddenError("approval must come from the same user"))

        approval = Approval(
            operation_id=proposal.operation_id,
            user_id=user_id,
            scope=self._scope(),
            proposal_version=proposal.version,
            confirmation_type=None,
            approved_at=approved_at,
        )
        new_state = replace(self, pending_proposal=proposal.consume(), updated_at=approved_at)
        return Result.success((approval, new_state))

    def approve_confirmation(
        self, user_id: UserId, operation_id: OperationId, approved_at: Timestamp
    ) -> Result[tuple[Approval, ConversationState], MangoError]:
        if self.pending_confirmation is None:
            return Result.failure(ConflictError("no pending confirmation"))
        confirmation = self.pending_confirmation
        if confirmation.operation_id != operation_id:
            return Result.failure(ConflictError("operation id does not match active confirmation"))
        if confirmation.consumed:
            return Result.failure(ConflictError("confirmation already consumed"))
        if confirmation.is_expired(approved_at):
            return Result.failure(ConflictError("confirmation has expired"))
        if self.participant.user_id != user_id:
            return Result.failure(ForbiddenError("approval must come from the same user"))

        approval = Approval(
            operation_id=confirmation.operation_id,
            user_id=user_id,
            scope=self._scope(),
            proposal_version=None,
            confirmation_type=confirmation.operation_type,
            approved_at=approved_at,
        )
        new_state = replace(
            self, pending_confirmation=confirmation.consume(), updated_at=approved_at
        )
        return Result.success((approval, new_state))

    def is_approval_valid(self, approval: Approval, now: Timestamp) -> bool:
        if approval.user_id != self.participant.user_id:
            return False
        if approval.scope != self._scope():
            return False
        if approval.proposal_version is not None:
            if self.pending_proposal is None:
                return False
            if self.pending_proposal.operation_id != approval.operation_id:
                return False
            if self.pending_proposal.version != approval.proposal_version:
                return False
            if self.pending_proposal.is_expired(now):
                return False
        if approval.confirmation_type is not None:
            if self.pending_confirmation is None:
                return False
            if self.pending_confirmation.operation_id != approval.operation_id:
                return False
            if self.pending_confirmation.is_expired(now):
                return False
        return True

    def _scope(self) -> str:
        return (
            f"{self.bot_id}:"
            f"{self.participant.provider.value}:"
            f"{self.participant.provider_user_id}"
        )
