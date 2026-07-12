"""Project application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.modules.conversation.domain import PendingConfirmation
from mango_agent.modules.conversation.ports import ConfirmationStore, ConversationKey
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.ports.repositories import (
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
from mango_agent.shared.ports.unit_of_work import UnitOfWorkFactory

CASCADE_BATCH_LIMIT = MAX_LIMIT


@final
@dataclass(frozen=True, slots=True)
class CreateProject:
    uow_factory: UnitOfWorkFactory

    async def __call__(self, actor: ActorScope, title: str) -> Result[Project, MangoError]:
        uow = self.uow_factory()
        try:
            await uow.begin()
            projects = uow.projects
            assert projects is not None
            project = Project.create(actor.user_id, title)
            created = await projects.create(actor, project)
            await uow.commit()
            return Result.success(created)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class GetProject:
    uow_factory: UnitOfWorkFactory

    async def __call__(
        self, actor: ActorScope, project_id: ProjectId
    ) -> Result[Project, MangoError]:
        uow = self.uow_factory()
        try:
            await uow.begin()
            projects = uow.projects
            assert projects is not None
            project = await projects.get(actor, project_id)
            await uow.commit()
            return Result.success(project)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class SearchProjects:
    uow_factory: UnitOfWorkFactory

    async def __call__(
        self,
        actor: ActorScope,
        title_contains: str | None = None,
        pagination: Pagination | None = None,
    ) -> Result[PaginatedResult[Project], MangoError]:
        uow = self.uow_factory()
        try:
            await uow.begin()
            projects = uow.projects
            assert projects is not None
            query = ProjectSearchQuery(
                owner_user_id=actor.user_id,
                title_contains=title_contains,
            )
            page = pagination if pagination is not None else Pagination.default()
            result = await projects.search(actor, query, page)
            await uow.commit()
            return Result.success(result)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class UpdateProject:
    uow_factory: UnitOfWorkFactory

    async def __call__(
        self, actor: ActorScope, project_id: ProjectId, title: str
    ) -> Result[Project, MangoError]:
        uow = self.uow_factory()
        try:
            await uow.begin()
            projects = uow.projects
            assert projects is not None
            project = await projects.get(actor, project_id)
            updated = project.rename(title)
            persisted = await projects.update(actor, updated)
            await uow.commit()
            return Result.success(persisted)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)


@final
@dataclass(frozen=True, slots=True)
class DeleteProject:
    uow_factory: UnitOfWorkFactory

    async def __call__(self, actor: ActorScope, project_id: ProjectId) -> Result[None, MangoError]:
        uow = self.uow_factory()
        try:
            await uow.begin()
            projects = uow.projects
            tasks = uow.tasks
            assert projects is not None
            assert tasks is not None

            project = await projects.get(actor, project_id)
            await self._cascade_soft_delete_tasks(actor, project.id, tasks)
            await projects.delete(actor, project.id)
            await uow.commit()
            return Result.success(None)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)
        except Exception as exc:
            await uow.rollback()
            return Result.failure(InternalError(str(exc)))

    async def _cascade_soft_delete_tasks(
        self, actor: ActorScope, project_id: ProjectId, task_repo: TaskRepository
    ) -> None:
        while True:
            child_tasks = await task_repo.search(
                actor,
                TaskSearchFilter(project_id=project_id),
                Pagination(limit=CASCADE_BATCH_LIMIT, offset=0),
            )
            if not child_tasks.items:
                return
            for task in child_tasks.items:
                await task_repo.delete(actor, task.id)


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
