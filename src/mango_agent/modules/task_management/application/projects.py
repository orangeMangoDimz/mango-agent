"""Project application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import InternalError, MangoError
from mango_agent.shared.domain.ids import ProjectId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import MAX_LIMIT, PaginatedResult, Pagination
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

    async def __call__(
        self, actor: ActorScope, project_id: ProjectId
    ) -> Result[None, MangoError]:
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

    async def _cascade_soft_delete_tasks(
        self, actor: ActorScope, project_id: ProjectId
    ) -> None:
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
