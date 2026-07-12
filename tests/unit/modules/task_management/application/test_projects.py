"""Unit tests for project application use cases."""

from __future__ import annotations

import typing
from datetime import timedelta

import pytest

from mango_agent.modules.conversation.domain import PendingConfirmation
from mango_agent.modules.conversation.ports import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.task_management.application.projects import (
    CreateProject,
    DeleteConfirmedProject,
    DeleteProject,
    GetProject,
    SearchProjects,
    UpdateProject,
)
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports.repositories import TaskSearchFilter
from mango_agent.shared.domain.errors import ConflictError, NotFoundError
from mango_agent.shared.domain.ids import OperationId, UserId
from mango_agent.shared.domain.value_objects import Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope

from ...conversation.fakes import FakeConfirmationStore
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
def uow(
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
) -> FakeUnitOfWork:
    return FakeUnitOfWork(
        project_repository=project_repo,
        task_repository=task_repo,
    )


@pytest.fixture
def uow_factory(
    uow: FakeUnitOfWork,
) -> typing.Callable[[], FakeUnitOfWork]:
    return lambda: uow


@pytest.fixture
def confirmation_store() -> FakeConfirmationStore:
    return FakeConfirmationStore()


@pytest.fixture
def conversation_key(owner: ActorScope) -> ConversationKey:
    return ConversationKey(
        provider=Provider.TELEGRAM,
        bot_id="test-bot",
        conversation_id="project-conversation",
        user_id=owner.user_id,
        command="test",
    )


async def test_create_project_normalizes_title(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    use_case = CreateProject(uow_factory=uow_factory)
    result = await use_case(owner, "  Mango  ")

    assert result.is_success
    assert result.value.title == "Mango"
    assert result.value.owner_user_id == owner.user_id


async def test_get_project_by_owner_succeeds(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    created = await CreateProject(uow_factory=uow_factory)(owner, "Mango")
    result = await GetProject(uow_factory=uow_factory)(owner, created.value.id)

    assert result.is_success
    assert result.value == created.value


async def test_get_project_cross_user_fails(
    owner: ActorScope,
    other: ActorScope,
    project_repo: FakeProjectRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    created = await CreateProject(uow_factory=uow_factory)(owner, "Mango")
    result = await GetProject(uow_factory=uow_factory)(other, created.value.id)

    assert result.is_failure
    assert isinstance(result.error, NotFoundError)


async def test_search_projects_scoped_to_actor(
    owner: ActorScope,
    other: ActorScope,
    project_repo: FakeProjectRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    create = CreateProject(uow_factory=uow_factory)
    await create(owner, "Owner Project")
    await create(other, "Other Project")

    result = await SearchProjects(uow_factory=uow_factory)(
        owner, title_contains="Owner", pagination=Pagination.default()
    )

    assert result.is_success
    assert result.value.total == 1
    assert result.value.items[0].title == "Owner Project"


async def test_update_project_title(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    created = await CreateProject(uow_factory=uow_factory)(owner, "Mango")
    result = await UpdateProject(uow_factory=uow_factory)(owner, created.value.id, "Mango 2")

    assert result.is_success
    assert result.value.title == "Mango 2"

    fetched = await GetProject(uow_factory=uow_factory)(owner, created.value.id)
    assert fetched.value.title == "Mango 2"


async def test_delete_project_cascades_soft_delete_to_child_tasks(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
    uow: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project = (await CreateProject(uow_factory=uow_factory)(owner, "Mango")).value
    task1 = Task.create(project.id, "Task 1")
    task2 = Task.create(project.id, "Task 2")
    await task_repo.create(owner, task1)
    await task_repo.create(owner, task2)

    result = await DeleteProject(uow_factory=uow_factory)(owner, project.id)

    assert result.is_success
    assert uow.begun
    assert uow.committed
    assert not uow.rolled_back
    assert project_repo.is_deleted(project.id)
    assert task_repo.is_deleted(task1.id)
    assert task_repo.is_deleted(task2.id)

    project_get = await GetProject(uow_factory=uow_factory)(owner, project.id)
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
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    created = await CreateProject(uow_factory=uow_factory)(owner, "Mango")
    project_id = created.value.id

    get_result = await GetProject(uow_factory=uow_factory)(other, project_id)
    assert get_result.is_failure

    update_result = await UpdateProject(uow_factory=uow_factory)(other, project_id, "Stolen")
    assert update_result.is_failure

    delete_result = await DeleteProject(uow_factory=uow_factory)(other, project_id)
    assert delete_result.is_failure

    search_result = await SearchProjects(uow_factory=uow_factory)(
        other, pagination=Pagination.default()
    )
    assert search_result.is_success
    assert search_result.value.total == 0


async def test_delete_project_requires_matching_confirmation(
    owner: ActorScope,
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
    uow: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
    confirmation_store: FakeConfirmationStore,
    conversation_key: ConversationKey,
) -> None:
    project = (await CreateProject(uow_factory=uow_factory)(owner, "Mango")).value
    delete_project = DeleteProject(uow_factory=uow_factory)
    use_case = DeleteConfirmedProject(delete_project, confirmation_store)

    missing = await use_case(owner, conversation_key, project.id, None)
    assert missing.is_failure
    assert isinstance(missing.error, ConflictError)
    assert not project_repo.is_deleted(project.id)

    operation_id = OperationId.generate()
    confirmation = PendingConfirmation.create(
        operation_id=operation_id,
        operation_type="delete_project",
        target_ref=str(project.id),
        expires_at=Timestamp.from_datetime(Timestamp.now().value + timedelta(hours=2)),
    )
    await confirmation_store.create(conversation_key, confirmation)

    deleted = await use_case(owner, conversation_key, project.id, operation_id)
    assert deleted.is_success
    assert project_repo.is_deleted(project.id)
