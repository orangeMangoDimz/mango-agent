"""Attachment storage port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, UserId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope

DEFAULT_PRESIGNED_URL_TTL_SECONDS = 300


@final
@dataclass(frozen=True, slots=True)
class UploadRequest:
    """Input for storing an attachment object."""

    content: bytes
    original_filename: str
    mime_type: str
    uploader_user_id: UserId

    def __post_init__(self) -> None:
        if not self.original_filename.strip():
            raise ValidationError("original filename must not be empty")
        if not self.mime_type.strip():
            raise ValidationError("mime type must not be empty")
        if not isinstance(self.uploader_user_id, UserId):
            raise ValidationError("uploader_user_id must be a UserId")


@final
@dataclass(frozen=True, slots=True)
class PresignedUrl:
    """Short-lived, authorized URL for an attachment object."""

    url: str
    expires_at: Timestamp

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValidationError("url must not be empty")


class AttachmentStorage(ABC):
    """Port for private object storage and authorized retrieval."""

    @abstractmethod
    async def upload(self, request: UploadRequest) -> str:
        """Store the attachment and return the stable object key."""

    @abstractmethod
    async def delete(self, object_key: str) -> None:
        """Remove the object; idempotent and safe to retry."""

    @abstractmethod
    async def generate_presigned_url(
        self,
        object_key: str,
        actor_scope: ActorScope,
        ttl_seconds: int = DEFAULT_PRESIGNED_URL_TTL_SECONDS,
    ) -> PresignedUrl:
        """Return a short-lived, authorized URL for the object."""

    @abstractmethod
    async def retrieve(self, object_key: str) -> bytes:
        """Return the raw object bytes."""


__all__ = [
    "Attachment",
    "AttachmentId",
    "AttachmentLifecycleStatus",
    "AttachmentStorage",
    "PresignedUrl",
    "StorageProvider",
    "UploadRequest",
]
