"""Pending proposal value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, OperationId
from mango_agent.shared.domain.value_objects import Timestamp


@final
@dataclass(frozen=True, slots=True)
class PendingProposal:
    operation_id: OperationId
    version: int
    content: str
    attachment_ids: tuple[AttachmentId, ...]
    created_at: Timestamp
    expires_at: Timestamp
    consumed: bool = False

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValidationError("proposal content must not be empty")
        if self.version < 1:
            raise ValidationError("proposal version must be at least 1")
        if self.expires_at.value <= self.created_at.value:
            raise ValidationError("expires_at must be after created_at")

    @classmethod
    def create(
        cls,
        operation_id: OperationId,
        content: str,
        attachment_ids: tuple[AttachmentId, ...] = (),
        expires_at: Timestamp | None = None,
    ) -> PendingProposal:
        now = Timestamp.now()
        if expires_at is None:
            raise ValidationError("expires_at is required")
        return cls(
            operation_id=operation_id,
            version=1,
            content=content.strip(),
            attachment_ids=attachment_ids,
            created_at=now,
            expires_at=expires_at,
            consumed=False,
        )

    def is_expired(self, now: Timestamp) -> bool:
        return now.value >= self.expires_at.value

    def consume(self) -> PendingProposal:
        return PendingProposal(
            operation_id=self.operation_id,
            version=self.version,
            content=self.content,
            attachment_ids=self.attachment_ids,
            created_at=self.created_at,
            expires_at=self.expires_at,
            consumed=True,
        )

    def revise(
        self,
        content: str,
        attachment_ids: tuple[AttachmentId, ...] = (),
        expires_at: Timestamp | None = None,
    ) -> PendingProposal:
        if expires_at is None:
            raise ValidationError("expires_at is required")
        now = Timestamp.now()
        return PendingProposal(
            operation_id=self.operation_id,
            version=self.version + 1,
            content=content.strip(),
            attachment_ids=attachment_ids,
            created_at=now,
            expires_at=expires_at,
            consumed=False,
        )
