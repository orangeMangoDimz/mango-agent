from __future__ import annotations

import pytest

from mango_agent.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InternalError,
    MangoError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_base_error_stores_message_and_code() -> None:
    err = MangoError("boom")
    assert err.message == "boom"
    assert err.code == "domain_error"
    assert str(err) == "boom"


def test_subclass_codes() -> None:
    assert ValidationError("x").code == "validation_error"
    assert NotFoundError("x").code == "not_found"
    assert ConflictError("x").code == "conflict"
    assert UnauthorizedError("x").code == "unauthorized"
    assert ForbiddenError("x").code == "forbidden"
    assert InternalError("x").code == "internal_error"


def test_subclasses_are_mango_errors() -> None:
    assert isinstance(ValidationError("x"), MangoError)


def test_errors_are_immutable() -> None:
    err = ValidationError("x")
    with pytest.raises(AttributeError):
        err.message = "y"
