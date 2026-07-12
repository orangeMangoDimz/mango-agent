"""Unit tests for attachment application use cases."""

from __future__ import annotations

import typing

import pytest

from mango_agent.modules.attachments.application.use_cases import (
    AuthorizeRetrieval,
    GenerateAccess,
    LinkAttachmentToTask,
    RegisterPendingUpload,
    RejectOrExpireAttachment,
)
from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
)
from mango_agent.modules.attachments.ports import UploadRequest
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InternalError,
    UnauthorizedError,
    ValidationError,
)
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.ports.actor_scope import ActorScope
from tests.unit.modules.attachments.fakes import (
    FakeAttachmentRepository,
    FakeAttachmentStorage,
    FakeTaskRepository,
    FakeUnitOfWork,
)


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")


@pytest.fixture
def storage() -> FakeAttachmentStorage:
    return FakeAttachmentStorage()


@pytest.fixture
def task_repo() -> FakeTaskRepository:
    return FakeTaskRepository()


@pytest.fixture
def attachment_repo(task_repo: FakeTaskRepository) -> FakeAttachmentRepository:
    return FakeAttachmentRepository(task_repo=task_repo)


@pytest.fixture
def uow_factory(
    attachment_repo: FakeAttachmentRepository,
    task_repo: FakeTaskRepository,
) -> typing.Callable[[], FakeUnitOfWork]:
    return lambda: FakeUnitOfWork(
        attachment_repository=attachment_repo,
        task_repository=task_repo,
    )


def _sample_request(actor: ActorScope) -> UploadRequest:
    return UploadRequest(
        content=b"image-content",
        original_filename="image.png",
        mime_type="image/png",
        uploader_user_id=actor.user_id,
    )


async def _uploaded_attachment(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> Attachment:
    use_case = RegisterPendingUpload(uow_factory=uow_factory, storage=storage)
    result = await use_case(actor, _sample_request(actor))
    assert result.is_success
    return result.value


async def _attached_attachment(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
    task_repo: FakeTaskRepository,
) -> tuple[Attachment, Task]:
    project = Project.create(owner_user_id=actor.user_id, title="Test Project")
    task_repo.add_project(project)
    task = Task.create(project_id=project.id, title="Test Task")
    task_repo.add_task(task)
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    linker = LinkAttachmentToTask(uow_factory=uow_factory)
    result = await linker(actor, attachment.id, task.id)
    assert result.is_success
    return result.value, task


async def test_register_pending_upload(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    use_case = RegisterPendingUpload(uow_factory=uow_factory, storage=storage)
    result = await use_case(actor, _sample_request(actor))

    assert result.is_success
    attachment = result.value
    assert attachment.uploader_user_id == actor.user_id
    assert attachment.lifecycle_status == AttachmentLifecycleStatus.UPLOADED
    assert storage.has_object(attachment.object_key)
    stored = await attachment_repo.get_authorized(actor, attachment.id)
    assert stored.id == attachment.id


async def test_register_pending_upload_rejects_actor_mismatch(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    other_actor = ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")
    use_case = RegisterPendingUpload(uow_factory=uow_factory, storage=storage)
    result = await use_case(other_actor, _sample_request(actor))

    assert result.is_failure
    assert isinstance(result.error, ForbiddenError)
    assert len(storage._objects) == 0


async def test_register_pending_upload_rejects_unsupported_mime_type(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    request = UploadRequest(
        content=b"content",
        original_filename="file.txt",
        mime_type="text/plain",
        uploader_user_id=actor.user_id,
    )
    use_case = RegisterPendingUpload(uow_factory=uow_factory, storage=storage)
    result = await use_case(actor, request)

    assert result.is_failure
    assert isinstance(result.error, ValidationError)
    assert len(storage._objects) == 0


async def test_compensation_on_persistence_failure(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment_repo.fail_next_register_pending()
    use_case = RegisterPendingUpload(uow_factory=uow_factory, storage=storage)
    result = await use_case(actor, _sample_request(actor))

    assert result.is_failure
    assert isinstance(result.error, InternalError)
    assert len(storage._objects) == 0
    assert len(attachment_repo._attachments) == 0


async def test_link_attachment_to_task(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    task_repo: FakeTaskRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project = Project.create(owner_user_id=actor.user_id, title="Test Project")
    task_repo.add_project(project)
    task = Task.create(project_id=project.id, title="Test Task")
    task_repo.add_task(task)
    attachment = await _uploaded_attachment(actor, storage, uow_factory)

    use_case = LinkAttachmentToTask(uow_factory=uow_factory)
    result = await use_case(actor, attachment.id, task.id)

    assert result.is_success
    linked = result.value
    assert linked.task_id == task.id
    assert linked.lifecycle_status == AttachmentLifecycleStatus.ATTACHED
    stored = await attachment_repo.get_authorized(actor, attachment.id)
    assert stored.task_id == task.id


async def test_link_attachment_to_task_rejects_unauthorized_task(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    task_repo: FakeTaskRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    project = Project.create(owner_user_id=UserId.generate(), title="Other Project")
    task_repo.add_project(project)
    task = Task.create(project_id=project.id, title="Other Task")
    task_repo.add_task(task)
    attachment = await _uploaded_attachment(actor, storage, uow_factory)

    use_case = LinkAttachmentToTask(uow_factory=uow_factory)
    result = await use_case(actor, attachment.id, task.id)

    assert result.is_failure
    assert isinstance(result.error, ForbiddenError)


async def test_authorize_retrieval_for_owner(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    use_case = AuthorizeRetrieval(uow_factory=uow_factory)

    result = await use_case(actor, attachment.id)

    assert result.is_success
    assert result.value.id == attachment.id


async def test_authorize_retrieval_cross_user_rejection(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    other_actor = ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")
    use_case = AuthorizeRetrieval(uow_factory=uow_factory)

    result = await use_case(other_actor, attachment.id)

    assert result.is_failure
    assert isinstance(result.error, UnauthorizedError)


async def test_generate_access_produces_presigned_url(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    use_case = GenerateAccess(uow_factory=uow_factory, storage=storage)

    result = await use_case(actor, attachment.id, ttl_seconds=120)

    assert result.is_success
    url = result.value
    assert attachment.object_key in url.url
    assert url.url.startswith("https://fake.storage/")
    # Presigned URLs are never persisted as attachment metadata.
    stored = await attachment_repo.get_authorized(actor, attachment.id)
    assert not hasattr(stored, "presigned_url")


async def test_generate_access_rejects_unauthorized_actor(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    other_actor = ActorScope(user_id=UserId.generate(), bot_id="test-bot", command="test")
    use_case = GenerateAccess(uow_factory=uow_factory, storage=storage)

    result = await use_case(other_actor, attachment.id)

    assert result.is_failure
    assert isinstance(result.error, UnauthorizedError)


async def test_reject_or_expire_attachment_triggers_cleanup(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    task_repo: FakeTaskRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment, _ = await _attached_attachment(actor, storage, uow_factory, task_repo)
    use_case = RejectOrExpireAttachment(uow_factory=uow_factory, storage=storage)

    result = await use_case(actor, attachment.id)

    assert result.is_success
    assert result.value.lifecycle_status == AttachmentLifecycleStatus.CLEANUP_PENDING
    assert not storage.has_object(attachment.object_key)
    assert storage.was_deleted(attachment.object_key)


async def test_reject_or_expire_uploaded_attachment_marks_rejected(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    use_case = RejectOrExpireAttachment(uow_factory=uow_factory, storage=storage)

    result = await use_case(actor, attachment.id)

    assert result.is_success
    assert result.value.lifecycle_status == AttachmentLifecycleStatus.REJECTED
    assert storage.has_object(attachment.object_key)


async def test_reject_or_expire_rejects_deleted_attachment(
    actor: ActorScope,
    storage: FakeAttachmentStorage,
    attachment_repo: FakeAttachmentRepository,
    uow_factory: typing.Callable[[], FakeUnitOfWork],
) -> None:
    attachment = await _uploaded_attachment(actor, storage, uow_factory)
    rejected = await attachment_repo.mark_lifecycle(
        actor, attachment.id, AttachmentLifecycleStatus.REJECTED
    )
    deleted = await attachment_repo.mark_lifecycle(
        actor, rejected.id, AttachmentLifecycleStatus.DELETED
    )
    use_case = RejectOrExpireAttachment(uow_factory=uow_factory, storage=storage)

    result = await use_case(actor, deleted.id)

    assert result.is_failure
    assert isinstance(result.error, ConflictError)
