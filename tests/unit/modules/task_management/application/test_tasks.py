"""Unit tests for task management application use cases."""

from __future__ import annotations

import typing
from datetime import timedelta

import pytest

from mango_agent.modules.conversation.domain import PendingConfirmation, PendingProposal
from mango_agent.modules.conversation.ports.state_store import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.task_management.application.tasks import (
    CreateApprovedTask,
    DeleteTask,
    GetTask,
    SearchTasks,
    TransitionTaskStatus,
    UpdateTask,
    UpdateTaskFields,
    ValidateTaskProposal,
)
from mango_agent.modules.task_management.domain import Priority, Status, Task
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.modules.task_management.ports.repositories import TaskSearchFilter
from mango_agent.shared.domain.errors import (
    ConflictError,
    InternalError,
    NotFoundError,
    ValidationError,
)
from mango_agent.shared.domain.ids import OperationId, ProjectId, UserId
from mango_agent.shared.domain.value_objects import Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey

from ...attachments.fakes import FakeAttachmentRepository
from ...conversation.fakes import FakeConfirmationStore, FakeProposalStore
from ..fakes import (
    FakeIdempotencyRepository,
    FakeProjectRepository,
    FakeTaskRepository,
    FakeUnitOfWork,
)

PROPOSAL_TTL_HOURS = 2
CONFIRMATION_TTL_HOURS = 2


def _expires_at() -> Timestamp:
    return Timestamp.from_datetime(Timestamp.now().value + timedelta(hours=PROPOSAL_TTL_HOURS))


@pytest.fixture
def owner() -> UserId:
    return UserId.generate()


@pytest.fixture
def other_user() -> UserId:
    return UserId.generate()


@pytest.fixture
def actor(owner: UserId) -> ActorScope:
    return ActorScope(user_id=owner, bot_id="test-bot", command="task")


@pytest.fixture
def other_actor(other_user: UserId) -> ActorScope:
    return ActorScope(user_id=other_user, bot_id="test-bot", command="task")


@pytest.fixture
def conversation_key(owner: UserId) -> ConversationKey:
    return ConversationKey(
        provider=Provider.TELEGRAM,
        bot_id="test-bot",
        conversation_id="conv-1",
        user_id=owner,
        command="task",
    )


@pytest.fixture
def project_repository() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def task_repository(project_repository: FakeProjectRepository) -> FakeTaskRepository:
    return FakeTaskRepository(project_repository)


@pytest.fixture
def attachment_repository() -> FakeAttachmentRepository:
    return FakeAttachmentRepository()


@pytest.fixture
def idempotency_repository() -> FakeIdempotencyRepository:
    return FakeIdempotencyRepository()


@pytest.fixture
def proposal_store() -> FakeProposalStore:
    return FakeProposalStore()


@pytest.fixture
def confirmation_store() -> FakeConfirmationStore:
    return FakeConfirmationStore()


@pytest.fixture
def unit_of_work(
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
) -> FakeUnitOfWork:
    return FakeUnitOfWork(
        project_repository=project_repository,
        task_repository=task_repository,
        attachment_repository=attachment_repository,
        idempotency_repository=idempotency_repository,
    )


@pytest.fixture
def uow_factory(
    unit_of_work: FakeUnitOfWork,
) -> typing.Callable[[], FakeUnitOfWork]:
    return lambda: unit_of_work


async def _create_project(
    actor: ActorScope, project_repository: FakeProjectRepository, title: str = "Groceries"
) -> ProjectId:
    from mango_agent.modules.task_management.domain import Project

    project = Project.create(owner_user_id=actor.user_id, title=title)
    await project_repository.create(actor, project)
    return project.id


async def _create_task(
    actor: ActorScope,
    task_repository: FakeTaskRepository,
    project_id: ProjectId,
    title: str = "Buy mangoes",
) -> Task:
    task = Task.create(project_id=project_id, title=title)
    return await task_repository.create(actor, task)


async def _seed_proposal(
    proposal_store: FakeProposalStore,
    conversation_key: ConversationKey,
    operation_id: OperationId,
    title: str = "Buy mangoes",
) -> PendingProposal:
    proposal = PendingProposal.create(
        operation_id=operation_id,
        content=f"Create task: {title}",
        expires_at=_expires_at(),
    )
    await proposal_store.create(conversation_key, proposal)
    return proposal


async def _seed_confirmation(
    confirmation_store: FakeConfirmationStore,
    conversation_key: ConversationKey,
    operation_id: OperationId,
    operation_type: str,
    target_ref: str,
) -> PendingConfirmation:
    confirmation = PendingConfirmation.create(
        operation_id=operation_id,
        operation_type=operation_type,
        target_ref=target_ref,
        expires_at=_expires_at(),
    )
    await confirmation_store.create(conversation_key, confirmation)
    return confirmation


async def test_validate_task_proposal_with_missing_project_info(
    actor: ActorScope,
) -> None:
    use_case = ValidateTaskProposal()
    result = await use_case(
        actor=actor,
        title="Buy mangoes",
        description="Get ripe ones",
        project_id=None,
        project_title=None,
    )

    assert result.is_success
    proposal = result.value
    assert proposal.needs_project_resolution
    assert proposal.title == "Buy mangoes"


async def test_create_approved_task_with_idempotency(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
    proposal_store: FakeProposalStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    operation_id = OperationId.generate()
    idempotency_key = IdempotencyKey(scope="approved_task", external_id=str(operation_id))
    proposal = await _seed_proposal(proposal_store, conversation_key, operation_id)

    use_case = CreateApprovedTask(
        proposal_store=proposal_store,
        uow_factory=uow_factory,
    )

    first = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=None,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert first.is_success
    created = first.value
    assert created.title == "Buy mangoes"
    assert unit_of_work.committed

    second = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=None,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert second.is_success
    assert second.value.id == created.id


async def test_create_approved_task_retries_after_transient_failure(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
    proposal_store: FakeProposalStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    operation_id = OperationId.generate()
    idempotency_key = IdempotencyKey(scope="approved_task", external_id=str(operation_id))
    proposal = await _seed_proposal(proposal_store, conversation_key, operation_id)
    task_repository.fail_next_create()

    use_case = CreateApprovedTask(
        proposal_store=proposal_store,
        uow_factory=uow_factory,
    )

    first = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=None,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert first.is_failure
    assert isinstance(first.error, InternalError)
    assert await idempotency_repository.lookup_operation(actor, idempotency_key) is not None

    second = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=None,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert second.is_success
    assert second.value.title == "Buy mangoes"
    assert unit_of_work.committed


async def test_create_approved_task_assigns_to_known_user(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
    proposal_store: FakeProposalStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    operation_id = OperationId.generate()
    idempotency_key = IdempotencyKey(scope="approved_task", external_id=str(operation_id))
    proposal = await _seed_proposal(proposal_store, conversation_key, operation_id)
    other_user = User.create("Bob")
    await unit_of_work.users.create(actor, other_user)

    use_case = CreateApprovedTask(
        proposal_store=proposal_store,
        uow_factory=uow_factory,
    )

    result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=other_user.id,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert result.is_success
    assert result.value.assigned_to == other_user.id


async def test_create_approved_task_rejects_unknown_assignee(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
    proposal_store: FakeProposalStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    operation_id = OperationId.generate()
    idempotency_key = IdempotencyKey(scope="approved_task", external_id=str(operation_id))
    proposal = await _seed_proposal(proposal_store, conversation_key, operation_id)
    unknown_user = User.create("Eve")

    use_case = CreateApprovedTask(
        proposal_store=proposal_store,
        uow_factory=uow_factory,
    )

    result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=proposal.version,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=unknown_user.id,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert result.is_failure
    assert isinstance(result.error, ValidationError)


async def test_create_approved_task_with_unapproved_proposal_fails(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    attachment_repository: FakeAttachmentRepository,
    idempotency_repository: FakeIdempotencyRepository,
    proposal_store: FakeProposalStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    operation_id = OperationId.generate()
    idempotency_key = IdempotencyKey(scope="approved_task", external_id=str(operation_id))

    use_case = CreateApprovedTask(
        proposal_store=proposal_store,
        uow_factory=uow_factory,
    )

    result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        operation_id=operation_id,
        proposal_version=1,
        title="Buy mangoes",
        description="",
        project_id=project_id,
        priority=Priority.MEDIUM,
        status=Status.TODO,
        assigned_to_user_id=None,
        attachment_ids=(),
        idempotency_key=idempotency_key,
    )
    assert result.is_failure
    assert isinstance(result.error, NotFoundError)


async def test_get_and_search_tasks_scoped_to_actor(
    actor: ActorScope,
    other_actor: ActorScope,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)

    get_use_case = GetTask(uow_factory=uow_factory)
    search_use_case = SearchTasks(uow_factory=uow_factory)

    get_result = await get_use_case(actor, task.id)
    assert get_result.is_success
    assert get_result.value.id == task.id

    search_result = await search_use_case(
        actor, TaskSearchFilter(project_id=project_id), Pagination.default()
    )
    assert search_result.is_success
    assert len(search_result.value.items) == 1

    other_get = await get_use_case(other_actor, task.id)
    assert other_get.is_failure
    assert isinstance(other_get.error, NotFoundError)

    other_search = await search_use_case(
        other_actor, TaskSearchFilter(project_id=project_id), Pagination.default()
    )
    assert other_search.is_success
    assert len(other_search.value.items) == 0


async def test_update_safe_fields_vs_sensitive_update(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    confirmation_store: FakeConfirmationStore,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)

    use_case = UpdateTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )

    safe = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        fields=UpdateTaskFields(
            tags=frozenset({"shopping"}),
            notes=(Note(user_text="Get ripe ones"),),
        ),
    )
    assert safe.is_success
    assert safe.value.tags == frozenset({"shopping"})
    assert len(safe.value.notes) == 1

    sensitive_without_confirmation = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        fields=UpdateTaskFields(title="Buy ripe mangoes"),
    )
    assert sensitive_without_confirmation.is_failure
    assert isinstance(sensitive_without_confirmation.error, ConflictError)

    confirmation_id = OperationId.generate()
    await _seed_confirmation(
        confirmation_store,
        conversation_key,
        confirmation_id,
        operation_type="task_sensitive_update",
        target_ref=str(task.id),
    )
    sensitive_with_confirmation = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        fields=UpdateTaskFields(
            title="Buy ripe mangoes",
            confirmation_operation_id=confirmation_id,
            confirmation_version=1,
        ),
    )
    assert sensitive_with_confirmation.is_success
    assert sensitive_with_confirmation.value.title == "Buy ripe mangoes"


async def test_update_task_assigns_to_known_user(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    confirmation_store: FakeConfirmationStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)
    other_user = User.create("Bob")
    await unit_of_work.users.create(actor, other_user)
    confirmation_id = OperationId.generate()
    await _seed_confirmation(
        confirmation_store,
        conversation_key,
        confirmation_id,
        operation_type="task_sensitive_update",
        target_ref=str(task.id),
    )

    use_case = UpdateTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )

    result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        fields=UpdateTaskFields(
            assigned_to=other_user.id,
            confirmation_operation_id=confirmation_id,
            confirmation_version=1,
        ),
    )
    assert result.is_success
    assert result.value.assigned_to == other_user.id


async def test_update_task_rejects_unknown_assignee(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    confirmation_store: FakeConfirmationStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)
    unknown_user = User.create("Eve")
    confirmation_id = OperationId.generate()
    await _seed_confirmation(
        confirmation_store,
        conversation_key,
        confirmation_id,
        operation_type="task_sensitive_update",
        target_ref=str(task.id),
    )

    use_case = UpdateTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )

    result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        fields=UpdateTaskFields(
            assigned_to=unknown_user.id,
            confirmation_operation_id=confirmation_id,
            confirmation_version=1,
        ),
    )
    assert result.is_failure
    assert isinstance(result.error, ValidationError)


async def test_transition_status_maintains_done_at(
    actor: ActorScope,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)

    use_case = TransitionTaskStatus(uow_factory=uow_factory)

    done_result = await use_case(actor, task.id, Status.DONE)
    assert done_result.is_success
    assert done_result.value.status == Status.DONE
    assert done_result.value.done_at is not None

    reopen_result = await use_case(actor, done_result.value.id, Status.IN_PROGRESS)
    assert reopen_result.is_success
    assert reopen_result.value.status == Status.IN_PROGRESS
    assert reopen_result.value.done_at is None


async def test_delete_task_requires_confirmation(
    actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    confirmation_store: FakeConfirmationStore,
    unit_of_work: FakeUnitOfWork,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)

    use_case = DeleteTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )

    without_confirmation = await use_case(
        actor=actor, conversation_key=conversation_key, task_id=task.id
    )
    assert without_confirmation.is_failure
    assert isinstance(without_confirmation.error, ConflictError)

    confirmation_id = OperationId.generate()
    await _seed_confirmation(
        confirmation_store,
        conversation_key,
        confirmation_id,
        operation_type="task_delete",
        target_ref=str(task.id),
    )
    delete_result = await use_case(
        actor=actor,
        conversation_key=conversation_key,
        task_id=task.id,
        confirmation_operation_id=confirmation_id,
    )
    assert delete_result.is_success
    assert unit_of_work.committed

    get_use_case = GetTask(uow_factory=uow_factory)
    after_delete = await get_use_case(actor, task.id)
    assert after_delete.is_failure
    assert isinstance(after_delete.error, NotFoundError)


async def test_cross_user_rejection(
    actor: ActorScope,
    other_actor: ActorScope,
    conversation_key: ConversationKey,
    project_repository: FakeProjectRepository,
    task_repository: FakeTaskRepository,
    confirmation_store: FakeConfirmationStore,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project_id = await _create_project(actor, project_repository)
    task = await _create_task(actor, task_repository, project_id)

    get_use_case = GetTask(uow_factory=uow_factory)
    update_use_case = UpdateTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )
    transition_use_case = TransitionTaskStatus(uow_factory=uow_factory)
    delete_use_case = DeleteTask(
        uow_factory=uow_factory,
        confirmation_store=confirmation_store,
    )
    search_use_case = SearchTasks(uow_factory=uow_factory)

    assert (await get_use_case(other_actor, task.id)).is_failure
    assert (
        await update_use_case(
            other_actor,
            conversation_key,
            task.id,
            UpdateTaskFields(tags=frozenset({"tag"})),
        )
    ).is_failure
    assert (await transition_use_case(other_actor, task.id, Status.IN_PROGRESS)).is_failure
    assert (await delete_use_case(other_actor, conversation_key, task.id)).is_failure
    search_result = await search_use_case(
        other_actor, TaskSearchFilter(project_id=project_id), Pagination.default()
    )
    assert len(search_result.value.items) == 0
