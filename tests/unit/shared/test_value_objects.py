from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.value_objects import (
    MAX_LIMIT,
    PaginatedResult,
    Pagination,
    Timestamp,
)


def test_timestamp_now_is_utc_aware() -> None:
    ts = Timestamp.now()
    assert ts.value.tzinfo is not None


def test_timestamp_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Timestamp(datetime(2024, 1, 1))


def test_timestamp_from_datetime() -> None:
    dt = datetime.now(tz=UTC)
    assert Timestamp.from_datetime(dt).value == dt


def test_pagination_valid() -> None:
    p = Pagination(limit=10, offset=5)
    assert p.limit == 10
    assert p.offset == 5


def test_pagination_default() -> None:
    p = Pagination.default()
    assert p.limit == 25
    assert p.offset == 0


def test_pagination_invalid_limit() -> None:
    with pytest.raises(ValidationError):
        Pagination(limit=0)


def test_pagination_limit_too_high() -> None:
    with pytest.raises(ValidationError):
        Pagination(limit=MAX_LIMIT + 1)


def test_pagination_invalid_offset() -> None:
    with pytest.raises(ValidationError):
        Pagination(limit=10, offset=-1)


def test_paginated_result_has_next() -> None:
    page = PaginatedResult(
        items=("a", "b"),
        total=5,
        pagination=Pagination(limit=2, offset=0),
    )
    assert page.has_next
    assert not page.has_previous


def test_paginated_result_page_size_exceeds_limit() -> None:
    with pytest.raises(ValidationError):
        PaginatedResult(
            items=("a", "b", "c"),
            total=3,
            pagination=Pagination(limit=2, offset=0),
        )
