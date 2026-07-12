"""Unit tests for project application use cases."""

from __future__ import annotations

import pytest

from mango_agent.modules.task_management.application.projects import (
    CreateProject,
    DeleteProject,
    GetProject,
    SearchProjects,
    UpdateProject,
)
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports.repositories import TaskSearchFilter
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Pagination
from mango_agent.shared.ports.actor_scope import ActorScope

from ..fakes import (
    FakeProjectRepository,
    FakeTaskRepository,
    FakeUnitOfWork,
)


@pytest.fixture
def owner() -> ActorScope:
    return ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")


@pytest.fixture
def other() -> ActorScope:
    return ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")


@pytest.fixture
def project_repo() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def task_repo(project_repo: FakeProjectRepository) -> FakeTaskRepository:
    return FakeTaskRepository(project_repo)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


async def test_create_project_normalizes_title(
    owner: ActorScope, project_repo: FakeProjectRepository
) -> None:
    use_case = CreateProject(project_repo)
    result = await use_case(owner, "  Mango  ")

    assert result.is_success
    assert result.value.title == "Mango"
    assert result.value.owner_user_id == owner.user_id


async def test_get_project_by_owner_succeeds(
    owner: ActorScope, project_repo: FakeProjectRepository
) -> None:
    created = await CreateProject(project_repo)(owner, "Mango")
    result = await GetProject(project_repo)(owner, created.value.id)

    assert result.is_success
    assert result.value == created.value


async def test_get_project_cross_user_fails(
    owner: ActorScope, other: ActorScope, project_repo: FakeProjectRepository
) -> None:
    created = await CreateProject(project_repo)(owner, "Mango")
    result = await GetProject(project_repo)(other, created.value.id)

    assert result.is_failure
    assert isinstance(result.error, NotFoundError)


async def test_search_projects_scoped_to_actor(
    owner: ActorScope, other: ActorScope, project_repo: FakeProjectRepository
) -> None:
    create = CreateProject(project_repo)
    await create(owner, "Owner Project")
    await create(other, "Other Project")

    result = await SearchProjects(project_repo)(
        owner, title_contains="Owner", pagination=Pagination.default()
    )

    assert result.is_success
    assert result.value.total == 1
    assert result.value.items[0].title == "Owner Project"


async def test_update_project_title(
    owner: ActorScope, project_repo: FakeProjectRepository
) -> None:
    created = await CreateProject(project_repo)(owner, "Mango")
    result = await UpdateProject(project_repo)(owner, created.value.id, "Mango 2")

    assert result.is_success
    assert result.value.title == "Mango 2"

    fetched = await GetProject(project_repo)(owner, created.value.id)
    assert fetched.value.title == "Mango 2"


async def test_delete_project_cascades_soft_delete_to_child_tasks(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
    uow: FakeUnitOfWork,
) -> None:
    project = (await CreateProject(project_repo)(owner, "Mango")).value
    task1 = Task.create(project.id, "Task 1")
    task2 = Task.create(project.id, "Task 2")
    await task_repo.create(owner, task1)
    await task_repo.create(owner, task2)

    result = await DeleteProject(uow, project_repo, task_repo)(owner, project.id)

    assert result.is_success
    assert uow.begun
    assert uow.committed
    assert not uow.rolled_back
    assert project_repo.is_deleted(project.id)
    assert task_repo.is_deleted(task1.id)
    assert task_repo.is_deleted(task2.id)

    project_get = await GetProject(project_repo)(owner, project.id)
    assert project_get.is_failure

    with pytest.raises(NotFoundError):
        await task_repo.get(owner, task1.id)
    with pytest.raises(NotFoundError):
        await task_repo.get(owner, task2.id)

    search_result = await task_repo.search(
        owner, TaskSearchFilter(project_id=project.id), Pagination.default()
    )
    assert search_result.total == 0


async def test_cross_user_rejection_for_all_operations(
    owner: ActorScope,
    other: ActorScope,
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
    uow: FakeUnitOfWork,
) -> None:
    created = await CreateProject(project_repo)(owner, "Mango")
    project_id = created.value.id

    get_result = await GetProject(project_repo)(other, project_id)
    assert get_result.is_failure

    update_result = await UpdateProject(project_repo)(other, project_id, "Stolen")
    assert update_result.is_failure

    delete_result = await DeleteProject(uow, project_repo, task_repo)(other, project_id)
    assert delete_result.is_failure

    search_result = await SearchProjects(project_repo)(other, pagination=Pagination.default())
    assert search_result.is_success
    assert search_result.value.total == 0


