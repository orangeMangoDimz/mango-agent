"""Conversation workflow application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.modules.conversation.domain import (
    Approval,
    ConversationState,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.conversation.ports import (
    ConfirmationStore,
    ConversationKey,
    ConversationStateStore,
    ProposalStore,
)
from mango_agent.shared.domain.errors import (
    ConflictError,
    InternalError,
    MangoError,
    NotFoundError,
)
from mango_agent.shared.domain.ids import AttachmentId, OperationId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import Timestamp


@final
@dataclass(frozen=True, slots=True)
class LoadScopedState:
    """Load the current conversation state and its optimistic version."""

    store: ConversationStateStore

    async def __call__(
        self, key: ConversationKey
    ) -> Result[tuple[ConversationState, int] | None, MangoError]:
        try:
            return Result.success(await self.store.load(key))
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class SaveScopedState:
    """Persist conversation state with optimistic concurrency."""

    store: ConversationStateStore

    async def __call__(
        self, key: ConversationKey, state: ConversationState, expected_version: int
    ) -> Result[bool, MangoError]:
        try:
            saved = await self.store.save(key, state, expected_version)
            if not saved:
                return Result.failure(ConflictError("stale version"))
            return Result.success(True)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class CreatePendingProposal:
    """Store a new pending proposal for a scoped conversation."""

    store: ProposalStore

    async def __call__(
        self,
        key: ConversationKey,
        operation_id: OperationId,
        content: str,
        attachment_ids: tuple[AttachmentId, ...] | list[AttachmentId],
        expires_at: Timestamp,
    ) -> Result[int, MangoError]:
        try:
            proposal = PendingProposal.create(
                operation_id=operation_id,
                content=content,
                attachment_ids=tuple(attachment_ids),
                expires_at=expires_at,
            )
            version = await self.store.create(key, proposal)
            return Result.success(version)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class ConsumeProposalApproval:
    """Atomically consume a pending proposal and return an approval."""

    store: ProposalStore

    async def __call__(
        self,
        key: ConversationKey,
        operation_id: OperationId,
        expected_version: int,
        approved_at: Timestamp,
    ) -> Result[Approval, MangoError]:
        try:
            current = await self.store.get(key)
            if current is None:
                return Result.failure(NotFoundError("no pending proposal"))

            proposal, version = current
            if proposal.operation_id != operation_id:
                return Result.failure(ConflictError("operation id does not match active proposal"))
            if proposal.is_expired(approved_at):
                return Result.failure(ConflictError("proposal has expired"))
            if proposal.consumed:
                return Result.failure(ConflictError("proposal already consumed"))
            if version != expected_version:
                return Result.failure(ConflictError("stale version"))

            consumed = await self.store.consume(key, operation_id, expected_version)
            if not consumed:
                return Result.failure(ConflictError("stale version"))

            approval = Approval(
                operation_id=proposal.operation_id,
                user_id=key.user_id,
                scope=str(key),
                proposal_version=proposal.version,
                confirmation_type=None,
                approved_at=approved_at,
            )
            return Result.success(approval)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class ReviseProposal:
    """Replace the existing pending proposal with a new version."""

    store: ProposalStore

    async def __call__(
        self,
        key: ConversationKey,
        content: str,
        attachment_ids: tuple[AttachmentId, ...] | list[AttachmentId],
        expires_at: Timestamp,
    ) -> Result[int, MangoError]:
        try:
            current = await self.store.get(key)
            if current is None:
                return Result.failure(NotFoundError("no pending proposal"))

            proposal, _ = current
            revised = proposal.revise(
                content=content,
                attachment_ids=tuple(attachment_ids),
                expires_at=expires_at,
            )
            await self.store.clear(key)
            version = await self.store.create(key, revised)
            return Result.success(version)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class CreatePendingConfirmation:
    """Store a new pending confirmation for a sensitive operation."""

    store: ConfirmationStore

    async def __call__(
        self,
        key: ConversationKey,
        operation_id: OperationId,
        operation_type: str,
        target_ref: str,
        expires_at: Timestamp,
    ) -> Result[int, MangoError]:
        try:
            confirmation = PendingConfirmation.create(
                operation_id=operation_id,
                operation_type=operation_type,
                target_ref=target_ref,
                expires_at=expires_at,
            )
            version = await self.store.create(key, confirmation)
            return Result.success(version)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class ConsumeConfirmation:
    """Atomically consume a pending confirmation and return an approval."""

    store: ConfirmationStore

    async def __call__(
        self,
        key: ConversationKey,
        operation_id: OperationId,
        expected_version: int,
        approved_at: Timestamp,
    ) -> Result[Approval, MangoError]:
        try:
            current = await self.store.get(key)
            if current is None:
                return Result.failure(NotFoundError("no pending confirmation"))

            confirmation, version = current
            if confirmation.operation_id != operation_id:
                return Result.failure(
                    ConflictError("operation id does not match active confirmation")
                )
            if confirmation.is_expired(approved_at):
                return Result.failure(ConflictError("confirmation has expired"))
            if confirmation.consumed:
                return Result.failure(ConflictError("confirmation already consumed"))
            if version != expected_version:
                return Result.failure(ConflictError("stale version"))

            consumed = await self.store.consume(key, operation_id, expected_version)
            if not consumed:
                return Result.failure(ConflictError("stale version"))

            approval = Approval(
                operation_id=confirmation.operation_id,
                user_id=key.user_id,
                scope=str(key),
                proposal_version=None,
                confirmation_type=confirmation.operation_type,
                approved_at=approved_at,
            )
            return Result.success(approval)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))


@final
@dataclass(frozen=True, slots=True)
class ClearCompletedOrRejectedState:
    """Clear all conversation state, proposals, and confirmations for a scope."""

    state_store: ConversationStateStore
    proposal_store: ProposalStore
    confirmation_store: ConfirmationStore

    async def __call__(self, key: ConversationKey) -> Result[None, MangoError]:
        try:
            await self.state_store.clear(key)
            await self.proposal_store.clear(key)
            await self.confirmation_store.clear(key)
            return Result.success(None)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(str(exc)))
