"""Attachment cleanup use case."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentEvent,
    AttachmentLifecycleStatus,
)
from mango_agent.modules.attachments.ports import AttachmentStorage
from mango_agent.shared.domain.errors import MangoError
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.unit_of_work import UnitOfWorkFactory


@final
@dataclass(frozen=True, slots=True)
class CleanupSummary:
    """Result of a cleanup run."""

    attachments_found: int = 0
    deleted: int = 0
    cleanup_pending: int = 0
    orphan_events_found: int = 0
    orphan_processed: int = 0
    orphan_failed: int = 0


@final
@dataclass(frozen=True, slots=True)
class CleanUpAttachments:
    """Idempotent cleanup of rejected/expired/orphaned attachments."""

    uow_factory: UnitOfWorkFactory
    storage: AttachmentStorage
    batch_size: int = 100

    async def __call__(self) -> Result[CleanupSummary, MangoError]:
        summary = CleanupSummary()
        now = Timestamp.now()

        async with self.uow_factory() as uow:
            attachments = await uow.attachments.list_cleanup_eligible(now, self.batch_size)
            summary = replace(summary, attachments_found=len(attachments))

        for attachment in attachments:
            summary = await self._process_attachment(attachment, summary)

        async with self.uow_factory() as uow:
            pending_events = await uow.attachment_events.list_pending(self.batch_size)
            summary = replace(summary, orphan_events_found=len(pending_events))

        for event in pending_events:
            summary = await self._process_orphan_event(event, summary)

        return Result.success(summary)

    async def _process_attachment(
        self,
        attachment: Attachment,
        summary: CleanupSummary,
    ) -> CleanupSummary:
        actor = ActorScope(
            user_id=attachment.uploader_user_id,
            bot_id="cleanup-worker",
            command="cleanup",
        )
        async with self.uow_factory() as uow:
            try:
                await self.storage.delete(attachment.object_key)
                await uow.attachments.mark_lifecycle(
                    actor,
                    attachment.id,
                    AttachmentLifecycleStatus.DELETED,
                )
                return replace(summary, deleted=summary.deleted + 1)
            except Exception:
                with suppress(Exception):
                    await uow.attachments.mark_lifecycle(
                        actor,
                        attachment.id,
                        AttachmentLifecycleStatus.CLEANUP_PENDING,
                    )
                return replace(summary, cleanup_pending=summary.cleanup_pending + 1)

    async def _process_orphan_event(
        self,
        event: AttachmentEvent,
        summary: CleanupSummary,
    ) -> CleanupSummary:
        try:
            await self.storage.delete(event.object_key)
            async with self.uow_factory() as uow:
                await uow.attachment_events.mark_processed(event.id)
            return replace(summary, orphan_processed=summary.orphan_processed + 1)
        except Exception:
            return replace(summary, orphan_failed=summary.orphan_failed + 1)
