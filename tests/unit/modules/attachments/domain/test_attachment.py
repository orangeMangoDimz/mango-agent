from __future__ import annotations

import pytest

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.shared.domain.errors import ConflictError, ValidationError
from mango_agent.shared.domain.ids import TaskId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


def _sample_attachment() -> Attachment:
    return Attachment.create(
        uploader_user_id=UserId.generate(),
        storage_provider=StorageProvider.R2,
        bucket_name="mango-attachments",
        object_key="tasks/abc/123/image.png",
        original_filename="image.png",
        mime_type="image/png",
        file_size=1024,
    )


def test_attachment_create() -> None:
    attachment = _sample_attachment()
    assert attachment.lifecycle_status == AttachmentLifecycleStatus.RECEIVED
    assert attachment.task_id is None


def test_attachment_empty_object_key_raises() -> None:
    with pytest.raises(ValidationError):
        Attachment.create(
            uploader_user_id=UserId.generate(),
            storage_provider=StorageProvider.R2,
            bucket_name="mango-attachments",
            object_key="   ",
            original_filename="image.png",
            mime_type="image/png",
            file_size=1024,
        )


def test_attachment_negative_file_size_raises() -> None:
    with pytest.raises(ValidationError):
        Attachment.create(
            uploader_user_id=UserId.generate(),
            storage_provider=StorageProvider.R2,
            bucket_name="mango-attachments",
            object_key="tasks/abc/123/image.png",
            original_filename="image.png",
            mime_type="image/png",
            file_size=-1,
        )


def test_attachment_legal_transition() -> None:
    attachment = _sample_attachment()
    uploaded = attachment.transition_to(AttachmentLifecycleStatus.UPLOADED)
    assert uploaded.lifecycle_status == AttachmentLifecycleStatus.UPLOADED


def test_attachment_illegal_transition_raises() -> None:
    attachment = _sample_attachment()
    with pytest.raises(ConflictError):
        attachment.transition_to(AttachmentLifecycleStatus.ATTACHED)


def test_attachment_attach_to_pending_metadata() -> None:
    attachment = _sample_attachment().transition_to(AttachmentLifecycleStatus.UPLOADED)
    attachment = attachment.transition_to(AttachmentLifecycleStatus.PENDING_METADATA)
    task_id = TaskId.generate()
    attached = attachment.attach_to(task_id)
    assert attached.task_id == task_id
    assert attached.lifecycle_status == AttachmentLifecycleStatus.ATTACHED


def test_attachment_attach_to_received_raises() -> None:
    attachment = _sample_attachment()
    with pytest.raises(ConflictError):
        attachment.attach_to(TaskId.generate())


def test_attachment_terminal_state_no_transitions() -> None:
    deleted = _sample_attachment().transition_to(AttachmentLifecycleStatus.DELETED)
    with pytest.raises(ConflictError):
        deleted.transition_to(AttachmentLifecycleStatus.UPLOADED)


def test_attachment_set_expires_at() -> None:
    attachment = _sample_attachment()
    expires = Timestamp.now()
    updated = attachment.set_expires_at(expires)
    assert updated.expires_at == expires
