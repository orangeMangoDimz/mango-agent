"""Task management application use cases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.conversation.domain import PendingConfirmation, PendingProposal
from mango_agent.modules.conversation.ports.state_store import (
    ConfirmationStore,
    ConversationKey,
    ProposalStore,
)
from mango_agent.modules.identity.ports.repositories import UserRepository, UserSearchQuery
from mango_agent.modules.task_management.domain import Priority, Status, Task
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import (
    ConflictError,
    MangoError,
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
from mango_agent.shared.domain.value_objects import (
    MAX_LIMIT,
    PaginatedResult,
    Pagination,
    Timestamp,
)
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey
from mango_agent.shared.ports.unit_of_work import UnitOfWorkFactory


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


async def _validate_assignee(
    actor: ActorScope,
    assigned_to_user_id: UserId | None,
    users: UserRepository,
) -> ValidationError | None:
    """Return an error if the assignee is not the actor or a known user."""
    if assigned_to_user_id is None or assigned_to_user_id == actor.user_id:
        return None
    result = await users.search(actor, UserSearchQuery(), Pagination(limit=MAX_LIMIT, offset=0))
    if not any(user.id == assigned_to_user_id for user in result.items):
        return ValidationError("assignee is not a known user")
    return None


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
    """Create a task after an independent proposal approval check.

    The operation id is used as the idempotency key for the business operation.
    The idempotency claim is first committed durably, then the task creation,
    attachment linking, and result recording run in a separate transaction.
    A repeated approval returns the previously created task; a transient failure
    leaves the claim in place so the next attempt retries the business operation.
    """

    def __init__(
        self,
        proposal_store: ProposalStore,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._proposal_store = proposal_store
        self._uow_factory = uow_factory

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
    ) -> Result[Task, MangoError]:
        proposal_result = await self._load_and_verify_proposal(
            conversation_key, operation_id, proposal_version
        )
        if proposal_result.is_failure:
            return Result.failure(proposal_result.error)

        proposal = proposal_result.value

        result = await self._create_task_in_transaction(
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
        if result.is_failure:
            return result

        # After the durable transaction commits, consume the Redis proposal.
        # If this fails, the task is already created; the next approval will
        # return the existing task via idempotency.
        consumed = await self._proposal_store.consume(
            conversation_key, operation_id, proposal.version
        )
        if not consumed:
            # Log warning but do not fail the already-persisted operation.
            pass

        return result

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
    ) -> Result[Task, MangoError]:
        # Phase 1: durable idempotency claim in its own transaction so a retry
        # after a transient business-operation failure can recover safely.
        existing_task = await self._claim_or_lookup_task(actor, idempotency_key, operation_id)
        if existing_task.is_failure:
            return Result.failure(existing_task.error)
        if existing_task.value is not None:
            return Result.success(existing_task.value)

        # Phase 2: create the task and record the result atomically.
        uow = self._uow_factory()
        try:
            await uow.begin()

            idempotency = uow.idempotency
            projects = uow.projects
            tasks = uow.tasks
            attachments = uow.attachments
            users = uow.users
            assert idempotency is not None
            assert projects is not None
            assert tasks is not None
            assert attachments is not None
            assert users is not None

            assignee_error = await _validate_assignee(actor, assigned_to_user_id, users)
            if assignee_error is not None:
                await uow.rollback()
                return Result.failure(assignee_error)

            await projects.get(actor, project_id)

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
            created = await tasks.create(actor, task)

            for attachment_id in attachment_ids:
                await attachments.link_to_task(actor, attachment_id, created.id)

            await idempotency.record_operation(actor, idempotency_key, operation_id)
            await idempotency.record_result(actor, idempotency_key, created.id)

            await uow.commit()
            return Result.success(created)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)

    async def _claim_or_lookup_task(
        self,
        actor: ActorScope,
        idempotency_key: IdempotencyKey,
        operation_id: OperationId,
    ) -> Result[Task | None, MangoError]:
        """Claim the idempotency key durably and return any completed task.

        Returns ``Result.success(None)`` when the key is newly claimed and the
        caller must execute the business operation. Returns a task when the
        operation was already completed. Failures roll back the claim
        transaction.
        """
        uow = self._uow_factory()
        try:
            await uow.begin()
            idempotency = uow.idempotency
            assert idempotency is not None

            existing = await idempotency.claim_event(actor, idempotency_key, operation_id)
            if existing is not None:
                result_resource_id = await idempotency.lookup_result(actor, idempotency_key)
                await uow.commit()
                if result_resource_id is None:
                    return Result.success(None)
                task_uow = self._uow_factory()
                try:
                    await task_uow.begin()
                    tasks = task_uow.tasks
                    assert tasks is not None
                    task = await tasks.get(actor, TaskId(result_resource_id.value))
                    await task_uow.commit()
                    return Result.success(task)
                except MangoError as exc:
                    await task_uow.rollback()
                    return Result.failure(exc)

            await uow.commit()
            return Result.success(None)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
class GetTask:
    """Return a single task if the actor is authorized."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self, actor: ActorScope, task_id: TaskId
    ) -> Result[Task, NotFoundError | UnauthorizedError]:
        uow = self._uow_factory()
        try:
            await uow.begin()
            tasks = uow.tasks
            projects = uow.projects
            assert tasks is not None
            assert projects is not None
            task = await tasks.get(actor, task_id)
            if not await self._is_authorized(actor, task, projects):
                await uow.rollback()
                return Result.failure(UnauthorizedError("not authorized to view task"))
            await uow.commit()
            return Result.success(task)
        except NotFoundError as exc:
            await uow.rollback()
            return Result.failure(exc)

    async def _is_authorized(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task, project_repository)

    async def _is_project_owner(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        try:
            project = await project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id


@final
class SearchTasks:
    """Search tasks scoped to the actor."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> Result[PaginatedResult[Task], NotFoundError]:
        uow = self._uow_factory()
        try:
            await uow.begin()
            tasks = uow.tasks
            assert tasks is not None
            result = await tasks.search(actor, criteria, pagination)
            await uow.commit()
            return Result.success(result)
        except NotFoundError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
class UpdateTask:
    """Apply safe updates directly; gate sensitive updates behind a confirmation."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        confirmation_store: ConfirmationStore,
    ) -> None:
        self._uow_factory = uow_factory
        self._confirmation_store = confirmation_store

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        task_id: TaskId,
        fields: UpdateTaskFields,
    ) -> Result[Task, ConflictError | NotFoundError | UnauthorizedError | ValidationError]:
        uow = self._uow_factory()
        try:
            await uow.begin()
            tasks = uow.tasks
            projects = uow.projects
            assert tasks is not None
            assert projects is not None

            task = await tasks.get(actor, task_id)
            if not await self._is_authorized(actor, task, projects):
                await uow.rollback()
                return Result.failure(UnauthorizedError("not authorized to update task"))

            if fields.assigned_to is not None:
                users = uow.users
                assert users is not None
                assignee_error = await _validate_assignee(actor, fields.assigned_to, users)
                if assignee_error is not None:
                    await uow.rollback()
                    return Result.failure(assignee_error)

            if self._is_sensitive_update(fields):
                confirmation_result = await self._consume_confirmation(
                    conversation_key, fields.confirmation_operation_id
                )
                if confirmation_result.is_failure:
                    await uow.rollback()
                    return Result.failure(confirmation_result.error)

            updated = self._apply_fields(actor, task, fields)
            if fields.project_id is not None and fields.project_id != task.project_id:
                await projects.get(actor, fields.project_id)
            persisted = await tasks.update(actor, updated)
            await uow.commit()
            return Result.success(persisted)
        except (NotFoundError, ValidationError, ConflictError) as exc:
            await uow.rollback()
            return Result.failure(exc)

    async def _is_authorized(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task, project_repository)

    async def _is_project_owner(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        try:
            project = await project_repository.get(actor, task.project_id)
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

    def _apply_fields(self, actor: ActorScope, task: Task, fields: UpdateTaskFields) -> Task:
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

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self, actor: ActorScope, task_id: TaskId, new_status: Status
    ) -> Result[Task, NotFoundError | UnauthorizedError | ValidationError]:
        uow = self._uow_factory()
        try:
            await uow.begin()
            tasks = uow.tasks
            projects = uow.projects
            assert tasks is not None
            assert projects is not None

            task = await tasks.get(actor, task_id)
            if not await self._is_authorized(actor, task, projects):
                await uow.rollback()
                return Result.failure(UnauthorizedError("not authorized to transition task"))

            updated = task.set_status(new_status)
            persisted = await tasks.update(actor, updated)
            await uow.commit()
            return Result.success(persisted)
        except (ValidationError, NotFoundError) as exc:
            await uow.rollback()
            return Result.failure(exc)

    async def _is_authorized(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        return await self._is_project_owner(actor, task, project_repository)

    async def _is_project_owner(
        self, actor: ActorScope, task: Task, project_repository: ProjectRepository
    ) -> bool:
        try:
            project = await project_repository.get(actor, task.project_id)
        except NotFoundError:
            return False
        return project.owner_user_id == actor.user_id


@final
class DeleteTask:
    """Soft-delete a task after explicit confirmation."""

    def __init__(
        self,
        confirmation_store: ConfirmationStore,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._confirmation_store = confirmation_store
        self._uow_factory = uow_factory

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        task_id: TaskId,
        confirmation_operation_id: OperationId | None = None,
    ) -> Result[None, ConflictError | NotFoundError | UnauthorizedError | ValidationError]:
        if confirmation_operation_id is None:
            return Result.failure(ConflictError("confirmation required to delete task"))

        confirmation_result = await self._consume_confirmation(
            conversation_key, confirmation_operation_id
        )
        if confirmation_result.is_failure:
            return Result.failure(confirmation_result.error)

        uow = self._uow_factory()
        try:
            await uow.begin()
            tasks = uow.tasks
            assert tasks is not None
            await tasks.delete(actor, task_id)
            await uow.commit()
        except (NotFoundError, ValidationError, ConflictError) as exc:
            await uow.rollback()
            return Result.failure(exc)

        return Result.success(None)

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
