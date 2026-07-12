"""Attachment repository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from mango_agent.modules.attachments.domain import Attachment, AttachmentLifecycleStatus
from mango_agent.shared.domain.ids import AttachmentId, TaskId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope

__all__ = ["AttachmentRepository"]


class AttachmentRepository(ABC):
    """Port for persisting and querying attachments."""

    @abstractmethod
    async def register_pending(
        self,
        actor: ActorScope,
        attachment: Attachment,
    ) -> Attachment:
        """Register a newly received attachment."""

    @abstractmethod
    async def link_to_task(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        task_id: TaskId,
    ) -> Attachment:
        """Attach an existing attachment to a task."""

    @abstractmethod
    async def get_authorized(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
    ) -> Attachment:
        """Return the attachment if the actor is authorized to view it."""

    @abstractmethod
    async def list_by_task(
        self,
        actor: ActorScope,
        task_id: TaskId,
        pagination: Pagination,
    ) -> PaginatedResult[Attachment]:
        """List attachments linked to a task."""

    @abstractmethod
    async def mark_lifecycle(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        new_status: AttachmentLifecycleStatus,
    ) -> Attachment:
        """Move the attachment to a new lifecycle status."""

    @abstractmethod
    async def list_cleanup_eligible(
        self,
        now: Timestamp,
        batch_size: int,
    ) -> Sequence[Attachment]:
        """Return attachments that are eligible for cleanup."""
