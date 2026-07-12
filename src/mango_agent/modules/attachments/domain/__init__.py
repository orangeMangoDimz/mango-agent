"""Attachment domain model."""

from __future__ import annotations

from mango_agent.modules.attachments.domain.attachment import Attachment
from mango_agent.modules.attachments.domain.enums import AttachmentLifecycleStatus, StorageProvider

__all__ = [
    "Attachment",
    "AttachmentLifecycleStatus",
    "StorageProvider",
]
