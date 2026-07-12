"""PostgreSQL implementation of the attachment repository port."""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.modules.attachments.ports.repositories import AttachmentRepository
from mango_agent.shared.domain.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from mango_agent.shared.domain.ids import AttachmentId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope


def _attachment_from_row(row: asyncpg.Record) -> Attachment:
    return Attachment(
        id=AttachmentId.from_string(str(row["id"])),
        uploader_user_id=UserId.from_string(str(row["uploader_user_id"])),
        task_id=TaskId.from_string(str(row["task_id"])) if row["task_id"] else None,
        storage_provider=StorageProvider(row["storage_provider"]),
        bucket_name=row["bucket_name"],
        object_key=row["object_key"],
        original_filename=row["original_filename"],
        mime_type=row["mime_type"],
        file_size=row["file_size"],
        lifecycle_status=AttachmentLifecycleStatus(row["lifecycle_status"]),
        expires_at=Timestamp.from_datetime(row["expires_at"]) if row["expires_at"] else None,
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
    )


class PostgresAttachmentRepository(AttachmentRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def register_pending(self, actor: ActorScope, attachment: Attachment) -> Attachment:
        try:
            await self._connection.execute(
                "INSERT INTO attachments (id, uploader_user_id, task_id, storage_provider, "
                "bucket_name, object_key, original_filename, mime_type, file_size, "
                "lifecycle_status, expires_at, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)",
                attachment.id.value,
                attachment.uploader_user_id.value,
                attachment.task_id.value if attachment.task_id else None,
                attachment.storage_provider.value,
                attachment.bucket_name,
                attachment.object_key,
                attachment.original_filename,
                attachment.mime_type,
                attachment.file_size,
                attachment.lifecycle_status.value,
                attachment.expires_at.value if attachment.expires_at else None,
                attachment.created_at.value,
                attachment.updated_at.value,
            )
        except UniqueViolationError as exc:
            raise ConflictError("attachment id already exists") from exc
        except ForeignKeyViolationError as exc:
            raise ValidationError("uploader or task does not exist") from exc
        return attachment

    async def link_to_task(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        task_id: TaskId,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        updated = attachment.attach_to(task_id)
        result = await self._connection.execute(
            "UPDATE attachments SET task_id = $1, lifecycle_status = $2, updated_at = $3 "
            "WHERE id = $4 AND uploader_user_id = $5",
            updated.task_id.value if updated.task_id else None,
            updated.lifecycle_status.value,
            updated.updated_at.value,
            updated.id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("attachment not found")
        return updated

    async def get_authorized(self, actor: ActorScope, attachment_id: AttachmentId) -> Attachment:
        row = await self._connection.fetchrow(
            "SELECT a.* FROM attachments a "
            "LEFT JOIN tasks t ON t.id = a.task_id "
            "LEFT JOIN projects p ON p.id = t.project_id "
            "WHERE a.id = $1 AND (a.uploader_user_id = $2 OR p.owner_user_id = $2)",
            attachment_id.value,
            actor.user_id.value,
        )
        if row is None:
            raise NotFoundError("attachment not found")
        return _attachment_from_row(row)

    async def list_by_task(
        self,
        actor: ActorScope,
        task_id: TaskId,
        pagination: Pagination,
    ) -> PaginatedResult[Attachment]:
        count_row = await self._connection.fetchrow(
            "SELECT COUNT(*) FROM attachments a "
            "JOIN tasks t ON t.id = a.task_id "
            "JOIN projects p ON p.id = t.project_id "
            "WHERE a.task_id = $1 AND (a.uploader_user_id = $2 OR p.owner_user_id = $2)",
            task_id.value,
            actor.user_id.value,
        )
        total = count_row["count"] if count_row else 0

        rows = await self._connection.fetch(
            "SELECT a.* FROM attachments a "
            "JOIN tasks t ON t.id = a.task_id "
            "JOIN projects p ON p.id = t.project_id "
            "WHERE a.task_id = $1 AND (a.uploader_user_id = $2 OR p.owner_user_id = $2) "
            "ORDER BY a.created_at DESC LIMIT $3 OFFSET $4",
            task_id.value,
            actor.user_id.value,
            pagination.limit,
            pagination.offset,
        )
        return PaginatedResult(
            items=tuple(_attachment_from_row(row) for row in rows),
            total=total,
            pagination=pagination,
        )

    async def mark_lifecycle(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        new_status: AttachmentLifecycleStatus,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        updated = attachment.transition_to(new_status)
        result = await self._connection.execute(
            "UPDATE attachments SET lifecycle_status = $1, updated_at = $2 "
            "WHERE id = $3 AND (uploader_user_id = $4 OR id = $3)",
            updated.lifecycle_status.value,
            updated.updated_at.value,
            updated.id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("attachment not found")
        return updated

    async def list_cleanup_eligible(
        self,
        now: Timestamp,
        batch_size: int,
    ) -> Sequence[Attachment]:
        rows = await self._connection.fetch(
            "SELECT * FROM attachments "
            "WHERE lifecycle_status = ANY($1) "
            "OR (lifecycle_status != 'Deleted' AND expires_at IS NOT NULL AND expires_at <= $2) "
            "ORDER BY created_at ASC LIMIT $3",
            [
                AttachmentLifecycleStatus.REJECTED.value,
                AttachmentLifecycleStatus.REJECTED_BY_VALIDATION.value,
                AttachmentLifecycleStatus.EXPIRED.value,
                AttachmentLifecycleStatus.ORPHANED.value,
                AttachmentLifecycleStatus.CLEANUP_PENDING.value,
            ],
            now.value,
            batch_size,
        )
        return tuple(_attachment_from_row(row) for row in rows)
