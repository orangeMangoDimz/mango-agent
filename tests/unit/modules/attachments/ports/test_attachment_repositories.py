"""Unit tests for the attachment repository port."""

from __future__ import annotations

import pytest

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.modules.attachments.ports.repositories import AttachmentRepository
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import AttachmentId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination
from mango_agent.shared.ports.actor_scope import ActorScope


class FakeAttachmentRepository(AttachmentRepository):
    def __init__(self) -> None:
        self._attachments: dict[AttachmentId, Attachment] = {}

    async def register_pending(
        self,
        actor: ActorScope,
        attachment: Attachment,
    ) -> Attachment:
        self._attachments[attachment.id] = attachment
        return attachment

    async def link_to_task(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        task_id: TaskId,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        linked = attachment.attach_to(task_id)
        self._attachments[attachment_id] = linked
        return linked

    async def get_authorized(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
    ) -> Attachment:
        attachment = self._attachments.get(attachment_id)
        if attachment is None:
            raise NotFoundError(f"attachment {attachment_id} not found")
        return attachment

    async def list_by_task(
        self,
        actor: ActorScope,
        task_id: TaskId,
        pagination: Pagination,
    ) -> PaginatedResult[Attachment]:
        items = tuple(a for a in self._attachments.values() if a.task_id == task_id)
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(page, len(items), pagination)

    async def mark_lifecycle(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        new_status: AttachmentLifecycleStatus,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        updated = attachment.transition_to(new_status)
        self._attachments[attachment_id] = updated
        return updated


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(
        user_id=UserId.generate(),
        bot_id="test-bot",
        command="test",
    )


@pytest.fixture
def repo() -> FakeAttachmentRepository:
    return FakeAttachmentRepository()


def _sample_attachment(actor: ActorScope) -> Attachment:
    return Attachment.create(
        uploader_user_id=actor.user_id,
        storage_provider=StorageProvider.R2,
        bucket_name="bucket",
        object_key="key",
        original_filename="mango.txt",
        mime_type="text/plain",
        file_size=100,
    )


async def test_register_pending_and_get(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
) -> None:
    attachment = _sample_attachment(actor)
    await repo.register_pending(actor, attachment)
    found = await repo.get_authorized(actor, attachment.id)
    assert found == attachment


async def test_link_to_task(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
) -> None:
    attachment = _sample_attachment(actor).transition_to(AttachmentLifecycleStatus.UPLOADED)
    await repo.register_pending(actor, attachment)
    task_id = TaskId.generate()
    linked = await repo.link_to_task(actor, attachment.id, task_id)
    assert linked.task_id == task_id
    assert linked.lifecycle_status == AttachmentLifecycleStatus.ATTACHED


async def test_list_by_task(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
) -> None:
    attachment = _sample_attachment(actor).transition_to(AttachmentLifecycleStatus.UPLOADED)
    await repo.register_pending(actor, attachment)
    task_id = TaskId.generate()
    await repo.link_to_task(actor, attachment.id, task_id)
    result = await repo.list_by_task(actor, task_id, Pagination.default())
    assert result.total == 1
    assert result.items[0].task_id == task_id


async def test_mark_lifecycle(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
) -> None:
    attachment = _sample_attachment(actor)
    await repo.register_pending(actor, attachment)
    updated = await repo.mark_lifecycle(actor, attachment.id, AttachmentLifecycleStatus.REJECTED)
    assert updated.lifecycle_status == AttachmentLifecycleStatus.REJECTED
