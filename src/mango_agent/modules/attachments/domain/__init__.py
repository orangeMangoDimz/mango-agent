"""Attachment domain model."""

from __future__ import annotations

from mango_agent.modules.attachments.domain.attachment import Attachment
from mango_agent.modules.attachments.domain.enums import AttachmentLifecycleStatus, StorageProvider
from mango_agent.modules.attachments.domain.events import (
    AttachmentEvent,
    AttachmentEventStatus,
    AttachmentEventType,
)

__all__ = [
    "Attachment",
    "AttachmentEvent",
    "AttachmentEventStatus",
    "AttachmentEventType",
    "AttachmentLifecycleStatus",
    "StorageProvider",
]
