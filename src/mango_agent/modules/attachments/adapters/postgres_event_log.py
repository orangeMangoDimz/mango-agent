"""PostgreSQL implementation of the attachment event log port."""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from mango_agent.modules.attachments.domain import (
    AttachmentEvent,
    AttachmentEventStatus,
    AttachmentEventType,
    StorageProvider,
)
from mango_agent.modules.attachments.ports.cleanup import AttachmentEventLog
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import AttachmentEventId, AttachmentId
from mango_agent.shared.domain.value_objects import Timestamp


def _event_from_row(row: asyncpg.Record) -> AttachmentEvent:
    attachment_id = (
        AttachmentId.from_string(str(row["attachment_id"])) if row["attachment_id"] else None
    )
    return AttachmentEvent(
        id=AttachmentEventId.from_string(str(row["id"])),
        attachment_id=attachment_id,
        object_key=row["object_key"],
        bucket_name=row["bucket_name"],
        storage_provider=StorageProvider(row["storage_provider"]),
        event_type=AttachmentEventType(row["event_type"]),
        status=AttachmentEventStatus(row["status"]),
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
        processed_at=Timestamp.from_datetime(row["processed_at"]) if row["processed_at"] else None,
    )


class PostgresAttachmentEventLog(AttachmentEventLog):
    """Durable outbox for attachment lifecycle events."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def record_event(self, event: AttachmentEvent) -> AttachmentEvent:
        await self._connection.execute(
            "INSERT INTO attachment_events (id, attachment_id, object_key, bucket_name, "
            "storage_provider, event_type, status, created_at, updated_at, processed_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            event.id.value,
            event.attachment_id.value if event.attachment_id else None,
            event.object_key,
            event.bucket_name,
            event.storage_provider.value,
            event.event_type.value,
            event.status.value,
            event.created_at.value,
            event.updated_at.value,
            event.processed_at.value if event.processed_at else None,
        )
        return event

    async def list_pending(self, limit: int) -> Sequence[AttachmentEvent]:
        rows = await self._connection.fetch(
            "SELECT * FROM attachment_events WHERE status = $1 ORDER BY created_at ASC LIMIT $2",
            AttachmentEventStatus.PENDING.value,
            limit,
        )
        return tuple(_event_from_row(row) for row in rows)

    async def mark_processed(self, event_id: AttachmentEventId) -> None:
        now = Timestamp.now()
        result = await self._connection.execute(
            "UPDATE attachment_events SET status = $1, processed_at = $2, updated_at = $3 "
            "WHERE id = $4",
            AttachmentEventStatus.PROCESSED.value,
            now.value,
            now.value,
            event_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("attachment event not found")
