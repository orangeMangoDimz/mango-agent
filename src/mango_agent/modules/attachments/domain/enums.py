"""Attachment domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class StorageProvider(StrEnum):
    R2 = "r2"


class AttachmentLifecycleStatus(StrEnum):
    RECEIVED = "Received"
    UPLOADED = "Uploaded"
    PENDING_METADATA = "PendingMetadata"
    ATTACHED = "Attached"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    ORPHANED = "Orphaned"
    CLEANUP_PENDING = "CleanupPending"
    DELETED = "Deleted"
    REJECTED_BY_VALIDATION = "RejectedByValidation"
