from __future__ import annotations

import uuid

import pytest

from mango_agent.shared.infrastructure.correlation import (
    _CORRELATION_ID,
    correlation_id_scope,
    get_correlation_id,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
def _reset_correlation_id() -> None:
    _CORRELATION_ID.set(None)
    yield
    _CORRELATION_ID.set(None)


def test_get_correlation_id_defaults_to_none() -> None:
    assert get_correlation_id() is None


def test_set_correlation_id() -> None:
    cid = set_correlation_id()
    assert get_correlation_id() == cid
    assert isinstance(cid, uuid.UUID)


def test_set_correlation_id_with_explicit_value() -> None:
    explicit = uuid.uuid4()
    set_correlation_id(explicit)
    assert get_correlation_id() == explicit


def test_correlation_id_scope_sets_and_resets() -> None:
    outer = get_correlation_id()
    with correlation_id_scope() as inner:
        assert get_correlation_id() == inner
    assert get_correlation_id() == outer


def test_correlation_id_scope_restores_previous_value() -> None:
    previous = uuid.uuid4()
    set_correlation_id(previous)
    with correlation_id_scope():
        assert get_correlation_id() != previous
    assert get_correlation_id() == previous
