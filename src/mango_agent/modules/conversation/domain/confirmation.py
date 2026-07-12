"""Pending confirmation value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import OperationId
from mango_agent.shared.domain.value_objects import Timestamp


@final
@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    operation_id: OperationId
    operation_type: str
    target_ref: str
    created_at: Timestamp
    expires_at: Timestamp
    consumed: bool = False

    def __post_init__(self) -> None:
        if not self.operation_type.strip():
            raise ValidationError("operation type must not be empty")
        if not self.target_ref.strip():
            raise ValidationError("target ref must not be empty")
        if self.expires_at.value <= self.created_at.value:
            raise ValidationError("expires_at must be after created_at")

    @classmethod
    def create(
        cls,
        operation_id: OperationId,
        operation_type: str,
        target_ref: str,
        expires_at: Timestamp | None = None,
    ) -> PendingConfirmation:
        now = Timestamp.now()
        if expires_at is None:
            raise ValidationError("expires_at is required")
        return cls(
            operation_id=operation_id,
            operation_type=operation_type.strip(),
            target_ref=target_ref.strip(),
            created_at=now,
            expires_at=expires_at,
            consumed=False,
        )

    def is_expired(self, now: Timestamp) -> bool:
        return now.value >= self.expires_at.value

    def consume(self) -> PendingConfirmation:
        return PendingConfirmation(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            target_ref=self.target_ref,
            created_at=self.created_at,
            expires_at=self.expires_at,
            consumed=True,
        )
