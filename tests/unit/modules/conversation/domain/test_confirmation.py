from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mango_agent.modules.conversation.domain.confirmation import PendingConfirmation
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import OperationId
from mango_agent.shared.domain.value_objects import Timestamp


def _future(seconds: int = 60) -> Timestamp:
    return Timestamp.from_datetime(datetime.now(tz=UTC) + timedelta(seconds=seconds))


def test_confirmation_create() -> None:
    confirmation = PendingConfirmation.create(
        OperationId.generate(), "delete_task", "task-123", expires_at=_future()
    )
    assert confirmation.operation_type == "delete_task"
    assert confirmation.target_ref == "task-123"
    assert confirmation.consumed is False


def test_confirmation_empty_operation_type_raises() -> None:
    with pytest.raises(ValidationError):
        PendingConfirmation.create(OperationId.generate(), "   ", "task-123", expires_at=_future())


def test_confirmation_empty_target_ref_raises() -> None:
    with pytest.raises(ValidationError):
        PendingConfirmation.create(
            OperationId.generate(), "delete_task", "   ", expires_at=_future()
        )


def test_confirmation_is_expired() -> None:
    confirmation = PendingConfirmation.create(
        OperationId.generate(), "delete_task", "task-123", expires_at=_future()
    )
    assert not confirmation.is_expired(Timestamp.now())
    assert confirmation.is_expired(_future(120))


def test_confirmation_consume() -> None:
    confirmation = PendingConfirmation.create(
        OperationId.generate(), "delete_task", "task-123", expires_at=_future()
    )
    consumed = confirmation.consume()
    assert consumed.consumed is True
