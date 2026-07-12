"""Shared value objects: timestamps, pagination, ordered result envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import final

from mango_agent.shared.domain.errors import ValidationError

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


@final
@dataclass(frozen=True, slots=True)
class Timestamp:
    """Timezone-aware point in time."""

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None:
            raise ValidationError("Timestamp must be timezone-aware")

    @classmethod
    def now(cls) -> Timestamp:
        return cls(datetime.now(tz=UTC))

    @classmethod
    def from_datetime(cls, value: datetime) -> Timestamp:
        return cls(value)

    def __str__(self) -> str:
        return self.value.isoformat()


@final
@dataclass(frozen=True, slots=True)
class Pagination:
    """Pagination parameters for list queries."""

    limit: int
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValidationError("limit must be greater than 0")
        if self.offset < 0:
            raise ValidationError("offset must be non-negative")
        if self.limit > MAX_LIMIT:
            raise ValidationError(f"limit must not exceed {MAX_LIMIT}")

    @classmethod
    def default(cls) -> Pagination:
        return cls(limit=DEFAULT_LIMIT, offset=0)


@final
@dataclass(frozen=True, slots=True)
class PaginatedResult[T]:
    """Ordered, paginated result envelope for list use cases."""

    items: tuple[T, ...]
    total: int
    pagination: Pagination

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValidationError("total must be non-negative")
        if len(self.items) > self.pagination.limit:
            raise ValidationError("page size cannot exceed pagination limit")

    @property
    def has_next(self) -> bool:
        return self.pagination.offset + len(self.items) < self.total

    @property
    def has_previous(self) -> bool:
        return self.pagination.offset > 0
