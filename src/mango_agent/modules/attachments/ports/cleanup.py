"""Ports for attachment cleanup and orphan event tracking."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from mango_agent.modules.attachments.domain import AttachmentEvent
from mango_agent.shared.domain.ids import AttachmentEventId

__all__ = ["AttachmentEventLog"]


class AttachmentEventLog(ABC):
    """Port for recording and querying attachment lifecycle events."""

    @abstractmethod
    async def record_event(self, event: AttachmentEvent) -> AttachmentEvent:
        """Persist a new attachment event."""

    @abstractmethod
    async def list_pending(self, limit: int) -> Sequence[AttachmentEvent]:
        """Return unprocessed events, oldest first."""

    @abstractmethod
    async def mark_processed(self, event_id: AttachmentEventId) -> None:
        """Mark an event as processed."""
