"""Attachment entity."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.attachments.domain.enums import AttachmentLifecycleStatus, StorageProvider
from mango_agent.shared.domain.errors import ConflictError, ValidationError
from mango_agent.shared.domain.ids import AttachmentId, TaskId, UserId
from mango_agent.shared.domain.value_objects import Timestamp

_VALID_TRANSITIONS = {
    AttachmentLifecycleStatus.RECEIVED: {
        AttachmentLifecycleStatus.UPLOADED,
        AttachmentLifecycleStatus.REJECTED,
        AttachmentLifecycleStatus.REJECTED_BY_VALIDATION,
        AttachmentLifecycleStatus.DELETED,
    },
    AttachmentLifecycleStatus.UPLOADED: {
        AttachmentLifecycleStatus.PENDING_METADATA,
        AttachmentLifecycleStatus.REJECTED,
        AttachmentLifecycleStatus.REJECTED_BY_VALIDATION,
    },
    AttachmentLifecycleStatus.PENDING_METADATA: {
        AttachmentLifecycleStatus.ATTACHED,
        AttachmentLifecycleStatus.ORPHANED,
        AttachmentLifecycleStatus.REJECTED_BY_VALIDATION,
    },
    AttachmentLifecycleStatus.ATTACHED: {
        AttachmentLifecycleStatus.ORPHANED,
        AttachmentLifecycleStatus.CLEANUP_PENDING,
        AttachmentLifecycleStatus.EXPIRED,
    },
    AttachmentLifecycleStatus.ORPHANED: {
        AttachmentLifecycleStatus.CLEANUP_PENDING,
        AttachmentLifecycleStatus.EXPIRED,
        AttachmentLifecycleStatus.ATTACHED,
    },
    AttachmentLifecycleStatus.CLEANUP_PENDING: {AttachmentLifecycleStatus.DELETED},
    AttachmentLifecycleStatus.REJECTED: {AttachmentLifecycleStatus.DELETED},
    AttachmentLifecycleStatus.REJECTED_BY_VALIDATION: {AttachmentLifecycleStatus.DELETED},
    AttachmentLifecycleStatus.EXPIRED: {
        AttachmentLifecycleStatus.CLEANUP_PENDING,
        AttachmentLifecycleStatus.DELETED,
    },
    AttachmentLifecycleStatus.DELETED: frozenset(),
}


@final
@dataclass(frozen=True, slots=True)
class Attachment:
    id: AttachmentId
    uploader_user_id: UserId
    task_id: TaskId | None
    storage_provider: StorageProvider
    bucket_name: str
    object_key: str
    original_filename: str
    mime_type: str
    file_size: int
    lifecycle_status: AttachmentLifecycleStatus
    expires_at: Timestamp | None
    created_at: Timestamp
    updated_at: Timestamp

    def __post_init__(self) -> None:
        if not isinstance(self.storage_provider, StorageProvider):
            raise ValidationError("storage_provider must be a StorageProvider value")
        if not self.bucket_name.strip():
            raise ValidationError("bucket name must not be empty")
        if not self.object_key.strip():
            raise ValidationError("object key must not be empty")
        if not self.original_filename.strip():
            raise ValidationError("original filename must not be empty")
        if not self.mime_type.strip():
            raise ValidationError("mime type must not be empty")
        if self.file_size < 0:
            raise ValidationError("file size must be non-negative")
        if not isinstance(self.lifecycle_status, AttachmentLifecycleStatus):
            raise ValidationError("lifecycle_status must be an AttachmentLifecycleStatus value")

    @classmethod
    def create(
        cls,
        uploader_user_id: UserId,
        storage_provider: StorageProvider,
        bucket_name: str,
        object_key: str,
        original_filename: str,
        mime_type: str,
        file_size: int,
    ) -> Attachment:
        now = Timestamp.now()
        return cls(
            id=AttachmentId.generate(),
            uploader_user_id=uploader_user_id,
            task_id=None,
            storage_provider=storage_provider,
            bucket_name=bucket_name.strip(),
            object_key=object_key.strip(),
            original_filename=original_filename.strip(),
            mime_type=mime_type.strip(),
            file_size=file_size,
            lifecycle_status=AttachmentLifecycleStatus.RECEIVED,
            expires_at=None,
            created_at=now,
            updated_at=now,
        )

    def transition_to(
        self, new_status: AttachmentLifecycleStatus, now: Timestamp | None = None
    ) -> Attachment:
        if not isinstance(new_status, AttachmentLifecycleStatus):
            raise ValidationError("new status must be an AttachmentLifecycleStatus value")
        if new_status not in _VALID_TRANSITIONS.get(self.lifecycle_status, frozenset()):
            raise ConflictError(
                f"cannot transition from {self.lifecycle_status.value} to {new_status.value}"
            )
        if now is None:
            now = Timestamp.now()
        return replace(self, lifecycle_status=new_status, updated_at=now)

    def attach_to(self, task_id: TaskId, now: Timestamp | None = None) -> Attachment:
        if self.lifecycle_status not in (
            AttachmentLifecycleStatus.PENDING_METADATA,
            AttachmentLifecycleStatus.UPLOADED,
        ):
            raise ConflictError(
                f"cannot attach while status is {self.lifecycle_status.value}"
            )
        if now is None:
            now = Timestamp.now()
        return replace(self, 
            task_id=task_id,
            lifecycle_status=AttachmentLifecycleStatus.ATTACHED,
            updated_at=now,
        )

    def set_expires_at(self, expires_at: Timestamp) -> Attachment:
        return replace(self, expires_at=expires_at, updated_at=Timestamp.now())
