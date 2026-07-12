"""Task management application use cases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.attachments.ports.repositories import AttachmentRepository
from mango_agent.modules.conversation.domain import PendingConfirmation, PendingProposal
from mango_agent.modules.conversation.ports.state_store import (
    ConfirmationStore,
    ConversationKey,
    ProposalStore,
)
from mango_agent.modules.task_management.domain import Priority, Status, Task
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mango_agent.shared.domain.ids import (
    AttachmentId,
    OperationId,
    ProjectId,
    TaskId,
    UserId,
)
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository
from mango_agent.shared.ports.unit_of_work import UnitOfWork


@final
@dataclass(frozen=True, slots=True)
class ValidatedTaskProposal:
    """Validated task proposal ready for workflow routing."""

    title: str
    description: str
    project_id: ProjectId | None
    project_title: str | None

    @property
    def needs_project_resolution(self) -> bool:
        return self.project_id is None and self.project_title is None


@final
@dataclass(frozen=True, slots=True)
class UpdateTaskFields:
    """Fields that may be updated on a task."""

    title: str | None = None
    description: str | None = None
    project_id: ProjectId | None = None
    priority: Priority | None = None
    assigned_to: UserId | None = None
    assigned_by: UserId | None = None
    tags: frozenset[str] | None = None
    notes: tuple[Note, ...] | None = None
    confirmation_operation_id: OperationId | None = None
    confirmation_version: int | None = None


@final
class ValidateTaskProposal:
    """Validate a raw task proposal and detect missing project context."""

    async def __call__(
        self,
        actor: ActorScope,
        title: str,
        description: str,
        project_id: ProjectId | None,
        project_title: str | None,
    ) -> Result[ValidatedTaskProposal, ValidationError]:
        if not title.strip():
            return Result.failure(ValidationError("task title is required"))

        return Result.success(
            ValidatedTaskProposal(
                title=title.strip(),
                description=description,
                project_id=project_id,
                project_title=project_title,
            )
        )


@final
class CreateApprovedTask:
    """Create a task after an independent proposal approval check."""

    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
        attachment_repository: AttachmentRepository,
        idempotency_repository: IdempotencyRepository,
        proposal_store: ProposalStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._task_repository = task_repository
        self._project_repository = project_repository
        self._attachment_repository = attachment_repository
        self._idempotency_repository = idempotency_repository
        self._proposal_store = proposal_store
        self._unit_of_work = unit_of_work

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        operation_id: OperationId,
        proposal_version: int,
        title: str,
        description: str,
        project_id: ProjectId,
        priority: Priority,
        status: Status,
        assigned_to_user_id: UserId | None,
        attachment_ids: tuple[AttachmentId, ...],
        idempotency_key: IdempotencyKey,
    ) -> Result[Task, ConflictError | NotFoundError | ValidationError]:
        proposal_result = await self._load_and_verify_proposal(
            conversation_key, operation_id, proposal_version
        )
        if proposal_result.is_failure:
            return Result.failure(proposal_result.error)

        existing_task = await self._lookup_existing_task(actor, idempotency_key)
        if existing_task is not None:
            return Result.success(existing_task)

        proposal = proposal_result.value
        if proposal.consumed:
            return Result.failure(ConflictError("proposal already consumed"))

        consumed = await self._proposal_store.consume(
            conversation_key, operation_id, proposal.version
        )
        if not consumed:
            return Result.failure(ConflictError("proposal could not be consumed"))

        return await self._create_task_in_transaction(
            actor,
            idempotency_key,
            operation_id,
            title,
            description,
            project_id,
            priority,
            status,
            assigned_to_user_id,
            attachment_ids,
        )

    async def _load_and_verify_proposal(
        self,
        conversation_key: ConversationKey,
        operation_id: OperationId,
        expected_version: int,
    ) -> Result[PendingProposal, ConflictError | NotFoundError | ValidationError]:
        stored = await self._proposal_store.get(conversation_key)
        if stored is None:
            return Result.failure(NotFoundError("no pending proposal"))

        proposal, _version = stored
        if proposal.operation_id != operation_id:
            return Result.failure(ConflictError("operation id does not match proposal"))
        if proposal.version != expected_version:
            return Result.failure(ConflictError("proposal version does not match"))
        if proposal.is_expired(Timestamp.now()):
            return Result.failure(ConflictError("proposal has expired"))

        return Result.success(proposal)

    async def _lookup_existing_task(
        self, actor: ActorScope, idempotency_key: IdempotencyKey
    ) -> Task | None:
        existing_operation_id = await self._idempotency_repository.claim_event(
            actor, idempotency_key
        )
        if existing_operation_id is None:
            return None

        result_resource_id = await self._idempotency_repository.lookup_result(
            actor, idempotency_key
        )
        if result_resource_id is None:
            return None

        try:
            task_id = TaskId(value=result_resource_id.value)
            return await self._task_repository.get(actor, task_id)
        except (NotFoundError, ValidationError):
            return None

    async def _create_task_in_transaction(
        self,
        actor: ActorScope,
        idempotency_key: IdempotencyKey,
        operation_id: OperationId,
        title: str,
        description: str,
        project_id: ProjectId,
        priority: Priority,
        status: Status,
        assigned_to_user_id: UserId | None,
        attachment_ids: tuple[AttachmentId, ...],
    ) -> Result[Task, ConflictError | NotFoundError | ValidationError]:
        try:
            await self._unit_of_work.begin()

            await self._project_repository.get(actor, project_id)

            assigned_by = actor.user_id if assigned_to_user_id is not None else None
            task = Task.create(
                project_id=project_id,
                title=title,
                description=description,
                priority=priority,
                status=status,
                assigned_by=assigned_by,
                assigned_to=assigned_to_user_id,
            )
            created = await self._task_repository.create(actor, task)

            for attachment_id in attachment_ids:
                await self._attachment_repository.link_to_task(
                    actor, attachment_id, created.id
                )

            await self._idempotency_repository.record_operation(
                actor, idempotency_key, operation_id
            )
            await self._idempotency_repository.record_result(
                actor, idempotency_key, created.id
            )

            await self._unit_of_work.commit()
            return Result.success(created)
        except (NotFoundError, ValidationError, ConflictError) as exc:
            await self._unit_of_work.rollback()
            return Result.failure(exc)


@final
class GetTask:
    """Return a single task if the actor is authorized."""

    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._task_repository = task_repository
        self._project_repository = project_repository

    async def __call__(
        self, actor: ActorScope, task_id: TaskId
    ) -> Result[Task, NotFoundError | UnauthorizedError]:
        try:
            task = await self._task_repository.get(actor, task_id)
        except NotFoundError as exc:
            return Result.failure(exc)

        if not await self._is_authorized(actor, task):
            return Result.failure(UnauthorizedError("not authorized to view task"))

        return Result.success(task)

    async def _is_authorized(self, actor: ActorScope, task: Task) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task)

    async def _is_project_owner(self, actor: ActorScope, task: Task) -> bool:
        try:
            project = await self._project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id


@final
class SearchTasks:
    """Search tasks scoped to the actor."""

    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def __call__(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> Result[PaginatedResult[Task], NotFoundError]:
        try:
            result = await self._task_repository.search(actor, criteria, pagination)
        except NotFoundError as exc:
            return Result.failure(exc)
        return Result.success(result)


@final
class UpdateTask:
    """Apply safe updates directly; gate sensitive updates behind a confirmation."""

    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
        confirmation_store: ConfirmationStore,
    ) -> None:
        self._task_repository = task_repository
        self._project_repository = project_repository
        self._confirmation_store = confirmation_store

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        task_id: TaskId,
        fields: UpdateTaskFields,
    ) -> Result[Task, ConflictError | NotFoundError | UnauthorizedError | ValidationError]:
        try:
            task = await self._task_repository.get(actor, task_id)
        except NotFoundError as exc:
            return Result.failure(exc)

        if not await self._is_authorized(actor, task):
            return Result.failure(UnauthorizedError("not authorized to update task"))

        if self._is_sensitive_update(fields):
            confirmation_result = await self._consume_confirmation(
                conversation_key, fields.confirmation_operation_id
            )
            if confirmation_result.is_failure:
                return Result.failure(confirmation_result.error)

        try:
            updated = self._apply_fields(actor, task, fields)
            if fields.project_id is not None and fields.project_id != task.project_id:
                await self._project_repository.get(actor, fields.project_id)
            persisted = await self._task_repository.update(actor, updated)
        except (NotFoundError, ValidationError, ConflictError) as exc:
            return Result.failure(exc)

        return Result.success(persisted)

    async def _is_authorized(self, actor: ActorScope, task: Task) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task)

    async def _is_project_owner(self, actor: ActorScope, task: Task) -> bool:
        try:
            project = await self._project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id

    def _is_sensitive_update(self, fields: UpdateTaskFields) -> bool:
        return any(
            (
                fields.title is not None,
                fields.description is not None,
                fields.project_id is not None,
                fields.assigned_to is not None,
                fields.assigned_by is not None,
            )
        )

    async def _consume_confirmation(
        self,
        conversation_key: ConversationKey,
        confirmation_operation_id: OperationId | None,
    ) -> Result[PendingConfirmation, ConflictError | NotFoundError | ValidationError]:
        if confirmation_operation_id is None:
            return Result.failure(ConflictError("confirmation required for sensitive update"))

        stored = await self._confirmation_store.get(conversation_key)
        if stored is None:
            return Result.failure(NotFoundError("no pending confirmation"))

        confirmation, version = stored
        if confirmation.operation_id != confirmation_operation_id:
            return Result.failure(ConflictError("confirmation operation id does not match"))
        if confirmation.is_expired(Timestamp.now()):
            return Result.failure(ConflictError("confirmation has expired"))
        if confirmation.consumed:
            return Result.failure(ConflictError("confirmation already consumed"))

        consumed = await self._confirmation_store.consume(
            conversation_key, confirmation_operation_id, version
        )
        if not consumed:
            return Result.failure(ConflictError("confirmation could not be consumed"))

        return Result.success(confirmation)

    def _apply_fields(
        self, actor: ActorScope, task: Task, fields: UpdateTaskFields
    ) -> Task:
        updated = task
        if fields.title is not None:
            updated = updated.rename(fields.title)
        if fields.description is not None:
            updated = updated.set_description(fields.description)
        if fields.project_id is not None and fields.project_id != task.project_id:
            updated = replace(
                updated,
                project_id=fields.project_id,
                updated_at=Timestamp.now(),
            )
        if fields.priority is not None:
            updated = updated.set_priority(fields.priority)
        if fields.assigned_to is not None:
            updated = updated.assign(
                assigned_by=fields.assigned_by or actor.user_id,
                assigned_to=fields.assigned_to,
            )
        if fields.tags is not None:
            updated = updated.set_tags(fields.tags)
        if fields.notes is not None:
            for note in fields.notes:
                updated = updated.add_note(note)
        return updated


@final
class TransitionTaskStatus:
    """Transition a task status while preserving the done_at invariant."""

    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._task_repository = task_repository
        self._project_repository = project_repository

    async def __call__(
        self, actor: ActorScope, task_id: TaskId, new_status: Status
    ) -> Result[Task, NotFoundError | UnauthorizedError | ValidationError]:
        try:
            task = await self._task_repository.get(actor, task_id)
        except NotFoundError as exc:
            return Result.failure(exc)

        if not await self._is_authorized(actor, task):
            return Result.failure(UnauthorizedError("not authorized to transition task"))

        try:
            updated = task.set_status(new_status)
            persisted = await self._task_repository.update(actor, updated)
        except (ValidationError, NotFoundError) as exc:
            return Result.failure(exc)

        return Result.success(persisted)

    async def _is_authorized(self, actor: ActorScope, task: Task) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task)

    async def _is_project_owner(self, actor: ActorScope, task: Task) -> bool:
        try:
            project = await self._project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id


@final
class DeleteTask:
    """Soft-delete a task after explicit confirmation."""

    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
        confirmation_store: ConfirmationStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._task_repository = task_repository
        self._project_repository = project_repository
        self._confirmation_store = confirmation_store
        self._unit_of_work = unit_of_work

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        task_id: TaskId,
        confirmation_operation_id: OperationId | None = None,
    ) -> Result[None, ConflictError | NotFoundError | UnauthorizedError | ValidationError]:
        if confirmation_operation_id is None:
            return Result.failure(ConflictError("confirmation required to delete task"))

        try:
            task = await self._task_repository.get(actor, task_id)
        except NotFoundError as exc:
            return Result.failure(exc)

        if not await self._is_authorized(actor, task):
            return Result.failure(UnauthorizedError("not authorized to delete task"))

        confirmation_result = await self._consume_confirmation(
            conversation_key, confirmation_operation_id
        )
        if confirmation_result.is_failure:
            return Result.failure(confirmation_result.error)

        try:
            await self._unit_of_work.begin()
            await self._task_repository.delete(actor, task_id)
            await self._unit_of_work.commit()
        except (NotFoundError, ValidationError, ConflictError) as exc:
            await self._unit_of_work.rollback()
            return Result.failure(exc)

        return Result.success(None)

    async def _is_authorized(self, actor: ActorScope, task: Task) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task)

    async def _is_project_owner(self, actor: ActorScope, task: Task) -> bool:
        try:
            project = await self._project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id

    async def _consume_confirmation(
        self,
        conversation_key: ConversationKey,
        confirmation_operation_id: OperationId,
    ) -> Result[PendingConfirmation, ConflictError | NotFoundError | ValidationError]:
        stored = await self._confirmation_store.get(conversation_key)
        if stored is None:
            return Result.failure(NotFoundError("no pending confirmation"))

        confirmation, version = stored
        if confirmation.operation_id != confirmation_operation_id:
            return Result.failure(ConflictError("confirmation operation id does not match"))
        if confirmation.is_expired(Timestamp.now()):
            return Result.failure(ConflictError("confirmation has expired"))
        if confirmation.consumed:
            return Result.failure(ConflictError("confirmation already consumed"))

        consumed = await self._confirmation_store.consume(
            conversation_key, confirmation_operation_id, version
        )
        if not consumed:
            return Result.failure(ConflictError("confirmation could not be consumed"))

        return Result.success(confirmation)
