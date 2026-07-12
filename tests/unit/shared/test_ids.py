from __future__ import annotations

import uuid

import pytest

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import (
    AttachmentId,
    OperationId,
    ProjectId,
    TaskId,
    UserId,
)


def test_generate_creates_unique_uuid() -> None:
    uid1 = UserId.generate()
    uid2 = UserId.generate()
    assert isinstance(uid1.value, uuid.UUID)
    assert uid1 != uid2


def test_ids_equal_when_same_uuid() -> None:
    raw = uuid.uuid4()
    assert UserId(raw) == UserId(raw)
    assert ProjectId(raw) == ProjectId(raw)


def test_different_types_with_same_uuid_are_not_equal() -> None:
    raw = uuid.uuid4()
    assert UserId(raw) != ProjectId(raw)


def test_from_string_parses_uuid() -> None:
    raw = uuid.uuid4()
    assert UserId.from_string(str(raw)).value == raw


def test_from_string_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        UserId.from_string("not-a-uuid")


def test_ids_are_hashable() -> None:
    raw = uuid.uuid4()
    assert len({UserId(raw), UserId(raw)}) == 1


def test_all_typed_ids_are_distinct() -> None:
    raw = uuid.uuid4()
    ids = {UserId(raw), ProjectId(raw), TaskId(raw), AttachmentId(raw), OperationId(raw)}
    assert len(ids) == 5
