"""Fakes for task-management unit tests."""

from __future__ import annotations

from mango_agent.modules.task_management.domain import Project, Status, Task
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import ConflictError, InternalError, NotFoundError
from mango_agent.shared.domain.ids import EntityId, OperationId, ProjectId, TaskId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository
from mango_agent.shared.ports.unit_of_work import UnitOfWork
from tests.unit.modules.attachments.fakes import FakeAttachmentRepository
from tests.unit.modules.identity.fakes import FakeUserRepository


class FakeProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[ProjectId, Project] = {}
        self._deleted: set[ProjectId] = set()

    async def create(self, actor: ActorScope, project: Project) -> Project:
        if project.id in self._projects:
            raise ConflictError("project id already exists")
        self._projects[project.id] = project
        return project

    async def get(self, actor: ActorScope, project_id: ProjectId) -> Project:
        if project_id in self._deleted:
            raise NotFoundError("project not found")
        project = self._projects.get(project_id)
        if project is None or project.owner_user_id != actor.user_id:
            raise NotFoundError("project not found")
        return project

    async def search(
        self,
        actor: ActorScope,
        query: ProjectSearchQuery,
        pagination: Pagination,
    ) -> PaginatedResult[Project]:
        items = [
            project
            for project in self._projects.values()
            if project.id not in self._deleted
            and project.owner_user_id == (query.owner_user_id or actor.user_id)
            and (
                query.title_contains is None
                or query.title_contains.lower() in project.title.lower()
            )
        ]
        total = len(items)
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(items=tuple(page), total=total, pagination=pagination)

    async def update(self, actor: ActorScope, project: Project) -> Project:
        if project.id in self._deleted or project.id not in self._projects:
            raise NotFoundError("project not found")
        existing = self._projects[project.id]
        if existing.owner_user_id != actor.user_id:
            raise NotFoundError("project not found")
        self._projects[project.id] = project
        return project

    async def delete(self, actor: ActorScope, project_id: ProjectId) -> None:
        project = await self.get(actor, project_id)
        self._deleted.add(project.id)

    def is_deleted(self, project_id: ProjectId) -> bool:
        return project_id in self._deleted


class FakeTaskRepository(TaskRepository):
    def __init__(self, project_repository: FakeProjectRepository | None = None) -> None:
        self._tasks: dict[TaskId, Task] = {}
        self._deleted: set[TaskId] = set()
        self._operation_tasks: dict[OperationId, TaskId] = {}
        self._project_repository = project_repository
        self._fail_next_create = False

    def fail_next_create(self) -> None:
        self._fail_next_create = True

    async def create(self, actor: ActorScope, task: Task) -> Task:
        if self._fail_next_create:
            self._fail_next_create = False
            raise InternalError("simulated transient create failure")
        if task.id in self._tasks:
            raise ConflictError("task id already exists")
        self._tasks[task.id] = task
        return task

    async def get(self, actor: ActorScope, task_id: TaskId) -> Task:
        if task_id in self._deleted:
            raise NotFoundError("task not found")
        task = self._tasks.get(task_id)
        if task is None or not self._is_visible(actor, task):
            raise NotFoundError("task not found")
        return task

    async def search(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> PaginatedResult[Task]:
        items = [
            task
            for task in self._tasks.values()
            if task.id not in self._deleted
            and self._is_visible(actor, task)
            and (criteria.project_id is None or task.project_id == criteria.project_id)
            and (criteria.status is None or task.status == criteria.status)
            and (criteria.priority is None or task.priority == criteria.priority)
            and (
                criteria.title_contains is None
                or criteria.title_contains.lower() in task.title.lower()
            )
            and (criteria.tags is None or bool(task.tags & criteria.tags))
        ]
        total = len(items)
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(items=tuple(page), total=total, pagination=pagination)

    async def update(self, actor: ActorScope, task: Task) -> Task:
        if task.id in self._deleted or task.id not in self._tasks:
            raise NotFoundError("task not found")
        existing = self._tasks[task.id]
        if not self._is_visible(actor, existing):
            raise NotFoundError("task not found")
        self._tasks[task.id] = task
        return task

    async def delete(self, actor: ActorScope, task_id: TaskId) -> None:
        task = self._tasks.get(task_id)
        if task is None or task.id in self._deleted or not self._is_visible(actor, task):
            raise NotFoundError("task not found")
        self._deleted.add(task_id)

    async def transition_status(
        self,
        actor: ActorScope,
        task_id: TaskId,
        new_status: Status,
    ) -> Task:
        task = await self.get(actor, task_id)
        updated = task.set_status(new_status)
        return await self.update(actor, updated)

    def _is_visible(self, actor: ActorScope, task: Task) -> bool:
        if actor.user_id == task.assigned_by or actor.user_id == task.assigned_to:
            return True
        if self._project_repository is None:
            return False
        project = self._project_repository._projects.get(task.project_id)
        return project is not None and project.owner_user_id == actor.user_id

    def record_operation_task(self, operation_id: OperationId, task_id: TaskId) -> None:
        self._operation_tasks[operation_id] = task_id

    def get_by_operation_id(self, operation_id: OperationId) -> Task | None:
        task_id = self._operation_tasks.get(operation_id)
        if task_id is None:
            return None
        return self._tasks.get(task_id)

    def is_deleted(self, task_id: TaskId) -> bool:
        return task_id in self._deleted


class FakeIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._operations: dict[IdempotencyKey, OperationId] = {}
        self._results: dict[IdempotencyKey, EntityId] = {}

    async def claim_event(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> OperationId | None:
        if key in self._operations:
            return self._operations[key]
        self._operations[key] = operation_id
        return None

    async def record_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> None:
        self._operations[key] = operation_id

    async def lookup_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        return self._operations.get(key)

    async def record_result(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        result_resource_id: EntityId,
    ) -> None:
        self._results[key] = result_resource_id

    async def lookup_result(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> EntityId | None:
        return self._results.get(key)


class FakeUnitOfWork(UnitOfWork):
    def __init__(
        self,
        project_repository: FakeProjectRepository | None = None,
        task_repository: FakeTaskRepository | None = None,
        attachment_repository: FakeAttachmentRepository | None = None,
        idempotency_repository: FakeIdempotencyRepository | None = None,
        user_repository: FakeUserRepository | None = None,
    ) -> None:
        self.projects = project_repository or FakeProjectRepository()
        self.tasks = task_repository or FakeTaskRepository(self.projects)
        self.attachments = attachment_repository or FakeAttachmentRepository()
        self.idempotency = idempotency_repository or FakeIdempotencyRepository()
        self.users = user_repository or FakeUserRepository()
        self.begun = False
        self.committed = False
        self.rolled_back = False

    async def begin(self) -> None:
        self.begun = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
