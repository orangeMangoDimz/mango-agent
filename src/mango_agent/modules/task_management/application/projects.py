"""Project application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.modules.conversation.domain import PendingConfirmation
from mango_agent.modules.conversation.ports import ConfirmationStore, ConversationKey
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import ConflictError, InternalError, MangoError, NotFoundError
from mango_agent.shared.domain.ids import OperationId, ProjectId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import (
    MAX_LIMIT,
    PaginatedResult,
    Pagination,
    Timestamp,
)
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.unit_of_work import UnitOfWork

CASCADE_BATCH_LIMIT = MAX_LIMIT


@final
@dataclass(frozen=True, slots=True)
class CreateProject:
    _repo: ProjectRepository

    async def __call__(self, actor: ActorScope, title: str) -> Result[Project, MangoError]:
        try:
            project = Project.create(actor.user_id, title)
            await self._repo.create(actor, project)
            return Result.success(project)
        except MangoError as exc:
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class GetProject:
    _repo: ProjectRepository

    async def __call__(
        self, actor: ActorScope, project_id: ProjectId
    ) -> Result[Project, MangoError]:
        try:
            project = await self._repo.get(actor, project_id)
            return Result.success(project)
        except MangoError as exc:
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class SearchProjects:
    _repo: ProjectRepository

    async def __call__(
        self,
        actor: ActorScope,
        title_contains: str | None = None,
        pagination: Pagination | None = None,
    ) -> Result[PaginatedResult[Project], MangoError]:
        try:
            query = ProjectSearchQuery(
                owner_user_id=actor.user_id,
                title_contains=title_contains,
            )
            page = pagination if pagination is not None else Pagination.default()
            result = await self._repo.search(actor, query, page)
            return Result.success(result)
        except MangoError as exc:
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class UpdateProject:
    _repo: ProjectRepository

    async def __call__(
        self, actor: ActorScope, project_id: ProjectId, title: str
    ) -> Result[Project, MangoError]:
        try:
            project = await self._repo.get(actor, project_id)
            updated = project.rename(title)
            persisted = await self._repo.update(actor, updated)
            return Result.success(persisted)
        except MangoError as exc:
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class DeleteProject:
    _uow: UnitOfWork
    _project_repo: ProjectRepository
    _task_repo: TaskRepository

    async def __call__(self, actor: ActorScope, project_id: ProjectId) -> Result[None, MangoError]:
        try:
            project = await self._project_repo.get(actor, project_id)
        except MangoError as exc:
            return Result.failure(exc)

        try:
            await self._uow.begin()
            await self._cascade_soft_delete_tasks(actor, project.id)
            await self._project_repo.delete(actor, project.id)
            await self._uow.commit()
            return Result.success(None)
        except MangoError as exc:
            await self._uow.rollback()
            return Result.failure(exc)
        except Exception as exc:
            await self._uow.rollback()
            return Result.failure(InternalError(str(exc)))

    async def _cascade_soft_delete_tasks(self, actor: ActorScope, project_id: ProjectId) -> None:
        while True:
            child_tasks = await self._task_repo.search(
                actor,
                TaskSearchFilter(project_id=project_id),
                Pagination(limit=CASCADE_BATCH_LIMIT, offset=0),
            )
            if not child_tasks.items:
                return
            for task in child_tasks.items:
                await self._task_repo.delete(actor, task.id)


@final
class DeleteConfirmedProject:
    """Delete a project only after consuming its scoped confirmation."""

    def __init__(
        self,
        delete_project: DeleteProject,
        confirmation_store: ConfirmationStore,
    ) -> None:
        self._delete_project = delete_project
        self._confirmation_store = confirmation_store

    async def __call__(
        self,
        actor: ActorScope,
        conversation_key: ConversationKey,
        project_id: ProjectId,
        confirmation_operation_id: OperationId | None,
    ) -> Result[None, MangoError]:
        if confirmation_operation_id is None:
            return Result.failure(ConflictError("confirmation required to delete project"))

        confirmation_result = await self._consume_confirmation(
            conversation_key,
            project_id,
            confirmation_operation_id,
        )
        if confirmation_result.is_failure:
            return Result.failure(confirmation_result.error)

        return await self._delete_project(actor, project_id)

    async def _consume_confirmation(
        self,
        conversation_key: ConversationKey,
        project_id: ProjectId,
        operation_id: OperationId,
    ) -> Result[PendingConfirmation, MangoError]:
        stored = await self._confirmation_store.get(conversation_key)
        if stored is None:
            return Result.failure(NotFoundError("no pending confirmation"))

        confirmation, version = stored
        if confirmation.operation_id != operation_id:
            return Result.failure(ConflictError("confirmation operation id does not match"))
        if confirmation.operation_type != "delete_project":
            return Result.failure(ConflictError("confirmation is not for project deletion"))
        if confirmation.target_ref != str(project_id):
            return Result.failure(ConflictError("confirmation target does not match project"))
        if confirmation.is_expired(Timestamp.now()):
            return Result.failure(ConflictError("confirmation has expired"))
        if confirmation.consumed:
            return Result.failure(ConflictError("confirmation already consumed"))

        consumed = await self._confirmation_store.consume(conversation_key, operation_id, version)
        if not consumed:
            return Result.failure(ConflictError("confirmation could not be consumed"))
        return Result.success(confirmation)
