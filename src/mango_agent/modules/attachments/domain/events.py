"""Attachment lifecycle events for outbox-style cleanup tracking."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import final

from mango_agent.modules.attachments.domain.enums import StorageProvider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentEventId, AttachmentId
from mango_agent.shared.domain.value_objects import Timestamp


class AttachmentEventType(StrEnum):
    UPLOAD_FAILED = "UploadFailed"


class AttachmentEventStatus(StrEnum):
    PENDING = "Pending"
    PROCESSED = "Processed"


@final
@dataclass(frozen=True, slots=True)
class AttachmentEvent:
    """A durable record of an attachment lifecycle event."""

    id: AttachmentEventId
    attachment_id: AttachmentId | None
    object_key: str
    bucket_name: str
    storage_provider: StorageProvider
    event_type: AttachmentEventType
    status: AttachmentEventStatus
    created_at: Timestamp
    updated_at: Timestamp
    processed_at: Timestamp | None

    def __post_init__(self) -> None:
        if not self.object_key.strip():
            raise ValidationError("object key must not be empty")
        if not self.bucket_name.strip():
            raise ValidationError("bucket name must not be empty")
        if not isinstance(self.storage_provider, StorageProvider):
            raise ValidationError("storage_provider must be a StorageProvider value")
        if not isinstance(self.event_type, AttachmentEventType):
            raise ValidationError("event_type must be an AttachmentEventType value")
        if not isinstance(self.status, AttachmentEventStatus):
            raise ValidationError("status must be an AttachmentEventStatus value")

    @classmethod
    def pending_upload_failed(
        cls,
        object_key: str,
        bucket_name: str,
        storage_provider: StorageProvider,
        attachment_id: AttachmentId | None = None,
    ) -> AttachmentEvent:
        now = Timestamp.now()
        return cls(
            id=AttachmentEventId.generate(),
            attachment_id=attachment_id,
            object_key=object_key.strip(),
            bucket_name=bucket_name.strip(),
            storage_provider=storage_provider,
            event_type=AttachmentEventType.UPLOAD_FAILED,
            status=AttachmentEventStatus.PENDING,
            created_at=now,
            updated_at=now,
            processed_at=None,
        )

    def mark_processed(self) -> AttachmentEvent:
        if self.status != AttachmentEventStatus.PENDING:
            raise ValidationError("only pending events can be marked processed")
        now = Timestamp.now()
        return replace(
            self,
            status=AttachmentEventStatus.PROCESSED,
            processed_at=now,
            updated_at=now,
        )
