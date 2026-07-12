"""Correlation ID carrier for request-scoped propagation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import UUID, uuid4

_CORRELATION_ID: ContextVar[UUID | None] = ContextVar("mango_correlation_id", default=None)


def get_correlation_id() -> UUID | None:
    return _CORRELATION_ID.get()


def set_correlation_id(correlation_id: UUID | None = None) -> UUID:
    if correlation_id is None:
        correlation_id = uuid4()
    _CORRELATION_ID.set(correlation_id)
    return correlation_id


@contextmanager
def correlation_id_scope(correlation_id: UUID | None = None) -> Iterator[UUID]:
    if correlation_id is None:
        correlation_id = uuid4()
    token: Token[UUID | None] = _CORRELATION_ID.set(correlation_id)
    try:
        yield correlation_id
    finally:
        _CORRELATION_ID.reset(token)
