"""Unit tests for task management repository ports."""

from __future__ import annotations

import pytest

from mango_agent.modules.task_management.domain.enums import Status
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import ProjectId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination
from mango_agent.shared.ports.actor_scope import ActorScope


class FakeProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[ProjectId, Project] = {}

    async def create(self, actor: ActorScope, project: Project) -> Project:
        self._projects[project.id] = project
        return project

    async def get(self, actor: ActorScope, project_id: ProjectId) -> Project:
        project = self._projects.get(project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    async def search(
        self,
        actor: ActorScope,
        query: ProjectSearchQuery,
        pagination: Pagination,
    ) -> PaginatedResult[Project]:
        items = tuple(
            p
            for p in self._projects.values()
            if (query.owner_user_id is None or p.owner_user_id == query.owner_user_id)
            and (query.title_contains is None or query.title_contains in p.title)
        )
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(page, len(items), pagination)

    async def update(self, actor: ActorScope, project: Project) -> Project:
        self._projects[project.id] = project
        return project

    async def delete(self, actor: ActorScope, project_id: ProjectId) -> None:
        if project_id not in self._projects:
            raise NotFoundError(f"project {project_id} not found")
        del self._projects[project_id]


class FakeTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self._tasks: dict[TaskId, Task] = {}

    async def create(self, actor: ActorScope, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    async def get(self, actor: ActorScope, task_id: TaskId) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError(f"task {task_id} not found")
        return task

    async def search(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> PaginatedResult[Task]:
        items = tuple(
            t
            for t in self._tasks.values()
            if (criteria.project_id is None or t.project_id == criteria.project_id)
            and (criteria.status is None or t.status == criteria.status)
            and (criteria.priority is None or t.priority == criteria.priority)
            and (criteria.title_contains is None or criteria.title_contains in t.title)
            and (criteria.tags is None or criteria.tags.issubset(t.tags))
        )
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(page, len(items), pagination)

    async def update(self, actor: ActorScope, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    async def delete(self, actor: ActorScope, task_id: TaskId) -> None:
        if task_id not in self._tasks:
            raise NotFoundError(f"task {task_id} not found")
        del self._tasks[task_id]

    async def transition_status(
        self,
        actor: ActorScope,
        task_id: TaskId,
        new_status: Status,
    ) -> Task:
        task = await self.get(actor, task_id)
        updated = task.set_status(new_status)
        self._tasks[task_id] = updated
        return updated


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(
        user_id=UserId.generate(),
        bot_id="test-bot",
        command="test",
    )


@pytest.fixture
def project_repo() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def task_repo() -> FakeTaskRepository:
    return FakeTaskRepository()


async def test_project_create_and_get(
    actor: ActorScope,
    project_repo: FakeProjectRepository,
) -> None:
    project = Project.create(actor.user_id, "Mango")
    await project_repo.create(actor, project)
    assert await project_repo.get(actor, project.id) == project


async def test_project_search_by_owner(
    actor: ActorScope,
    project_repo: FakeProjectRepository,
) -> None:
    project = Project.create(actor.user_id, "Mango")
    await project_repo.create(actor, project)
    result = await project_repo.search(
        actor,
        ProjectSearchQuery(owner_user_id=actor.user_id),
        Pagination.default(),
    )
    assert result.total == 1
    assert result.items == (project,)


async def test_project_update_and_delete(
    actor: ActorScope,
    project_repo: FakeProjectRepository,
) -> None:
    project = Project.create(actor.user_id, "Mango")
    await project_repo.create(actor, project)
    renamed = project.rename("Mango 2")
    updated = await project_repo.update(actor, renamed)
    assert updated.title == "Mango 2"
    await project_repo.delete(actor, project.id)
    with pytest.raises(NotFoundError):
        await project_repo.get(actor, project.id)


async def test_task_create_and_get(
    actor: ActorScope,
    task_repo: FakeTaskRepository,
) -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    await task_repo.create(actor, task)
    assert await task_repo.get(actor, task.id) == task


async def test_task_transition_status(
    actor: ActorScope,
    task_repo: FakeTaskRepository,
) -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    await task_repo.create(actor, task)
    updated = await task_repo.transition_status(actor, task.id, Status.DONE)
    assert updated.status == Status.DONE
    assert updated.done_at is not None


async def test_task_search_by_status(
    actor: ActorScope,
    task_repo: FakeTaskRepository,
) -> None:
    task = Task.create(
        ProjectId.generate(),
        "Buy mangoes",
        status=Status.IN_PROGRESS,
    )
    await task_repo.create(actor, task)
    result = await task_repo.search(
        actor,
        TaskSearchFilter(status=Status.IN_PROGRESS),
        Pagination.default(),
    )
    assert result.total == 1
    assert result.items[0].status == Status.IN_PROGRESS
