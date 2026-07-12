"""Unit tests for the attachment cleanup use case."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import final

import pytest

from mango_agent.modules.attachments.application.cleanup import CleanUpAttachments, CleanupSummary
from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentEvent,
    AttachmentEventStatus,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.modules.attachments.ports.cleanup import AttachmentEventLog
from mango_agent.modules.attachments.ports.repositories import AttachmentRepository
from mango_agent.modules.attachments.ports.storage import (
    AttachmentStorage,
    PresignedUrl,
    UploadRequest,
)
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import AttachmentEventId, AttachmentId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope


@final
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

    async def list_cleanup_eligible(
        self,
        now: Timestamp,
        batch_size: int,
    ) -> Sequence[Attachment]:
        eligible_statuses = {
            AttachmentLifecycleStatus.REJECTED,
            AttachmentLifecycleStatus.REJECTED_BY_VALIDATION,
            AttachmentLifecycleStatus.EXPIRED,
            AttachmentLifecycleStatus.ORPHANED,
            AttachmentLifecycleStatus.CLEANUP_PENDING,
        }
        items = tuple(
            a
            for a in self._attachments.values()
            if a.lifecycle_status in eligible_statuses
            or (a.expires_at is not None and a.expires_at <= now)
        )
        return items[:batch_size]


@final
class FakeAttachmentEventLog(AttachmentEventLog):
    def __init__(self) -> None:
        self._events: dict[AttachmentEventId, AttachmentEvent] = {}

    async def record_event(self, event: AttachmentEvent) -> AttachmentEvent:
        self._events[event.id] = event
        return event

    async def list_pending(self, limit: int) -> Sequence[AttachmentEvent]:
        items = sorted(
            (e for e in self._events.values() if e.status == AttachmentEventStatus.PENDING),
            key=lambda e: e.created_at.value,
        )
        return tuple(items[:limit])

    async def mark_processed(self, event_id: AttachmentEventId) -> None:
        event = self._events.get(event_id)
        if event is None:
            raise NotFoundError("event not found")
        self._events[event_id] = event.mark_processed()


@final
@dataclass(frozen=True, slots=True)
class FakeUnitOfWork:
    attachments: FakeAttachmentRepository
    attachment_events: FakeAttachmentEventLog

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


@final
@dataclass(frozen=True, slots=True)
class FakeAttachmentStorage(AttachmentStorage):
    _fail_keys: set[str] = field(default_factory=set)
    deleted: set[str] = field(default_factory=set)

    async def upload(self, request: UploadRequest) -> str:
        return "fake-key"

    async def delete(self, object_key: str) -> None:
        if object_key in self._fail_keys:
            raise RuntimeError(f"delete failed for {object_key}")
        self.deleted.add(object_key)

    async def generate_presigned_url(
        self,
        object_key: str,
        actor_scope: ActorScope,
        ttl_seconds: int = 300,
    ) -> PresignedUrl:
        return PresignedUrl(url="http://example.com/fake", expires_at=Timestamp.now())

    async def retrieve(self, object_key: str) -> bytes:
        return b""


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


@pytest.fixture
def events() -> FakeAttachmentEventLog:
    return FakeAttachmentEventLog()


@pytest.fixture
def uow_factory(repo: FakeAttachmentRepository, events: FakeAttachmentEventLog):
    return lambda: FakeUnitOfWork(attachments=repo, attachment_events=events)


@pytest.fixture
def storage() -> FakeAttachmentStorage:
    return FakeAttachmentStorage()


@pytest.fixture
def use_case(
    uow_factory,
    storage: FakeAttachmentStorage,
) -> CleanUpAttachments:
    return CleanUpAttachments(uow_factory=uow_factory, storage=storage, batch_size=10)


def _sample_attachment(actor: ActorScope, status: AttachmentLifecycleStatus) -> Attachment:
    attachment = Attachment.create(
        uploader_user_id=actor.user_id,
        storage_provider=StorageProvider.R2,
        bucket_name="bucket",
        object_key=f"key-{status.value}",
        original_filename="mango.txt",
        mime_type="text/plain",
        file_size=100,
    )
    if status == AttachmentLifecycleStatus.RECEIVED:
        return attachment
    return attachment.transition_to(status)


async def test_cleanup_deletes_eligible(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
    use_case: CleanUpAttachments,
    storage: FakeAttachmentStorage,
) -> None:
    attachment = _sample_attachment(actor, AttachmentLifecycleStatus.REJECTED)
    await repo.register_pending(actor, attachment)

    result = await use_case()

    assert result.is_success
    summary = result.value
    assert summary == CleanupSummary(attachments_found=1, deleted=1)
    updated = await repo.get_authorized(actor, attachment.id)
    assert updated.lifecycle_status == AttachmentLifecycleStatus.DELETED
    assert attachment.object_key in storage.deleted


async def test_cleanup_marks_cleanup_pending_on_delete_failure(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
    storage: FakeAttachmentStorage,
    use_case: CleanUpAttachments,
) -> None:
    attachment = _sample_attachment(actor, AttachmentLifecycleStatus.REJECTED)
    await repo.register_pending(actor, attachment)
    storage = replace(storage, _fail_keys={attachment.object_key})
    use_case = CleanUpAttachments(
        uow_factory=lambda: FakeUnitOfWork(repo, FakeAttachmentEventLog()),
        storage=storage,
        batch_size=10,
    )

    result = await use_case()

    assert result.is_success
    assert result.value == CleanupSummary(attachments_found=1, cleanup_pending=1)
    updated = await repo.get_authorized(actor, attachment.id)
    assert updated.lifecycle_status == AttachmentLifecycleStatus.CLEANUP_PENDING


async def test_cleanup_is_idempotent(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
    use_case: CleanUpAttachments,
) -> None:
    attachment = _sample_attachment(actor, AttachmentLifecycleStatus.REJECTED)
    await repo.register_pending(actor, attachment)

    first = await use_case()
    second = await use_case()

    assert first.value == CleanupSummary(attachments_found=1, deleted=1)
    assert second.value == CleanupSummary(attachments_found=0, deleted=0)
    updated = await repo.get_authorized(actor, attachment.id)
    assert updated.lifecycle_status == AttachmentLifecycleStatus.DELETED


async def test_cleanup_processes_orphan_events(
    actor: ActorScope,
    repo: FakeAttachmentRepository,
    events: FakeAttachmentEventLog,
    storage: FakeAttachmentStorage,
    uow_factory,
) -> None:
    event = AttachmentEvent.pending_upload_failed(
        object_key="orphan-key",
        bucket_name="bucket",
        storage_provider=StorageProvider.R2,
    )
    await events.record_event(event)
    use_case = CleanUpAttachments(uow_factory=uow_factory, storage=storage, batch_size=10)

    result = await use_case()

    assert result.value == CleanupSummary(orphan_events_found=1, orphan_processed=1)
    assert "orphan-key" in storage.deleted
    processed = await events.list_pending(10)
    assert len(processed) == 0


async def test_cleanup_leaves_orphan_events_on_failure(
    actor: ActorScope,
    events: FakeAttachmentEventLog,
    storage: FakeAttachmentStorage,
    uow_factory,
) -> None:
    event = AttachmentEvent.pending_upload_failed(
        object_key="orphan-key",
        bucket_name="bucket",
        storage_provider=StorageProvider.R2,
    )
    await events.record_event(event)
    storage = replace(storage, _fail_keys={"orphan-key"})
    use_case = CleanUpAttachments(uow_factory=uow_factory, storage=storage, batch_size=10)

    result = await use_case()

    assert result.value == CleanupSummary(orphan_events_found=1, orphan_failed=1)
    pending = await events.list_pending(10)
    assert len(pending) == 1
