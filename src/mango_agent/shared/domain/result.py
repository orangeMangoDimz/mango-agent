"""Immutable result type for use-case outcomes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeIs, final

from mango_agent.shared.domain.errors import MangoError


class _Missing:
    __slots__ = ()


_MISSING = _Missing()


def _is_value_present[T](value: T | _Missing) -> TypeIs[T]:
    return value is not _MISSING


def _is_error_present[E: MangoError](error: E | _Missing) -> TypeIs[E]:
    return error is not _MISSING


@final
@dataclass(frozen=True, slots=True)
class Result[T, E: MangoError]:
    _value: T | _Missing = _MISSING
    _error: E | _Missing = _MISSING

    def __post_init__(self) -> None:
        if _is_value_present(self._value) == _is_error_present(self._error):
            raise ValueError("Result must contain exactly one of value or error")

    @classmethod
    def success(cls, value: T) -> Result[T, E]:
        return cls(value, _MISSING)

    @classmethod
    def failure(cls, error: E) -> Result[T, E]:
        return cls(_MISSING, error)

    @property
    def is_success(self) -> bool:
        return _is_value_present(self._value)

    @property
    def is_failure(self) -> bool:
        return not _is_value_present(self._value)

    @property
    def value(self) -> T:
        if _is_value_present(self._value):
            return self._value
        raise ValueError("Result is a failure")

    @property
    def error(self) -> E:
        if _is_error_present(self._error):
            return self._error
        raise ValueError("Result is a success")

    def map[U](self, fn: Callable[[T], U]) -> Result[U, E]:
        if _is_value_present(self._value):
            return Result.success(fn(self._value))
        if not _is_error_present(self._error):
            raise RuntimeError("unreachable")
        return Result.failure(self._error)

    def bind[U](self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
        if _is_value_present(self._value):
            return fn(self._value)
        if not _is_error_present(self._error):
            raise RuntimeError("unreachable")
        return Result.failure(self._error)

    def map_error[F: MangoError](self, fn: Callable[[E], F]) -> Result[T, F]:
        if _is_error_present(self._error):
            return Result.failure(fn(self._error))
        if not _is_value_present(self._value):
            raise RuntimeError("unreachable")
        return Result.success(self._value)

    def unwrap_or(self, default: T) -> T:
        if _is_value_present(self._value):
            return self._value
        return default

    def __repr__(self) -> str:
        if self.is_success:
            return f"Result.success({self._value!r})"
        return f"Result.failure({self._error!r})"
