from __future__ import annotations

import pytest

from mango_agent.modules.identity.domain.user import User
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId


def test_user_create() -> None:
    user = User.create("Dimas")
    assert isinstance(user.id, UserId)
    assert user.display_name == "Dimas"
    assert user.created_at == user.updated_at


def test_user_empty_display_name_raises() -> None:
    with pytest.raises(ValidationError):
        User.create("   ")


def test_user_update_display_name() -> None:
    user = User.create("Dimas")
    before = user.updated_at
    user.update_display_name("Alex")
    assert user.display_name == "Alex"
    assert user.updated_at is not before


def test_user_update_display_name_empty_raises() -> None:
    user = User.create("Dimas")
    before = user.updated_at
    with pytest.raises(ValidationError):
        user.update_display_name("   ")
    assert user.display_name == "Dimas"
    assert user.updated_at is before


def test_user_created_at_unchanged_on_update() -> None:
    user = User.create("Dimas")
    created_at = user.created_at
    user.update_display_name("Alex")
    assert user.created_at is created_at
