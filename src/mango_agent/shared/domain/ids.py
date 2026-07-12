"""Typed UUID-based ID value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self, final
from uuid import UUID, uuid4

from mango_agent.shared.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class EntityId:
    """Base for strongly typed entity IDs. Subclass once per aggregate root."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValidationError(
                f"{type(self).__name__} value must be a UUID, got {type(self.value).__name__}"
            )

    @classmethod
    def generate(cls) -> Self:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> Self:
        try:
            return cls(value=UUID(value))
        except ValueError as exc:
            raise ValidationError(f"Invalid {cls.__name__}: {value}") from exc

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(value={self.value!r})"


@final
class UserId(EntityId):
    """Identifies an internal user."""


@final
class ProjectId(EntityId):
    """Identifies a project."""


@final
class TaskId(EntityId):
    """Identifies a task."""


@final
class AttachmentId(EntityId):
    """Identifies an attachment."""


@final
class AttachmentEventId(EntityId):
    """Identifies an attachment lifecycle event."""


@final
class OperationId(EntityId):
    """Identifies a business operation / idempotency scope."""
