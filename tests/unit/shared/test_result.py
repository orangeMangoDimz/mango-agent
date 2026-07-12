from __future__ import annotations

import pytest

from mango_agent.shared.domain.errors import InternalError, ValidationError
from mango_agent.shared.domain.result import _MISSING, Result


def test_success_result() -> None:
    r = Result.success(42)
    assert r.is_success
    assert not r.is_failure
    assert r.value == 42


def test_failure_result() -> None:
    err = ValidationError("bad")
    r = Result.failure(err)
    assert not r.is_success
    assert r.is_failure
    assert r.error == err


def test_failure_result_value_raises() -> None:
    err = ValidationError("bad")
    r = Result.failure(err)
    with pytest.raises(ValueError):
        _ = r.value


def test_success_result_error_raises() -> None:
    r = Result.success(42)
    with pytest.raises(ValueError):
        _ = r.error


def test_invalid_result_raises() -> None:
    err = ValidationError("bad")
    with pytest.raises(ValueError):
        Result(_MISSING, _MISSING)
    with pytest.raises(ValueError):
        Result(42, err)


def test_success_with_none_value() -> None:
    r = Result.success(None)
    assert r.is_success
    assert r.value is None


def test_map_success() -> None:
    r = Result.success(2).map(lambda x: x * 3)
    assert r.is_success
    assert r.value == 6


def test_map_failure() -> None:
    err = ValidationError("bad")
    r = Result.failure(err).map(lambda x: x * 3)
    assert r.is_failure
    assert r.error == err


def test_bind_success() -> None:
    r = Result.success(2).bind(lambda x: Result.success(x * 3))
    assert r.is_success
    assert r.value == 6


def test_bind_failure() -> None:
    err = ValidationError("bad")
    r = Result.failure(err).bind(lambda x: Result.success(x * 3))
    assert r.is_failure
    assert r.error == err


def test_map_error() -> None:
    err = ValidationError("bad")
    r = Result.failure(err).map_error(lambda e: InternalError(e.message))
    assert r.is_failure
    assert r.error.code == "internal_error"


def test_unwrap_or() -> None:
    assert Result.success(2).unwrap_or(0) == 2
    assert Result.failure(ValidationError("bad")).unwrap_or(0) == 0


def test_result_is_immutable() -> None:
    r = Result.success(42)
    with pytest.raises(AttributeError):
        r._value = 0
