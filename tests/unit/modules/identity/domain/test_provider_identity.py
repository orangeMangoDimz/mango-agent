from __future__ import annotations

import pytest

from mango_agent.modules.identity.domain.ids import ProviderIdentityId
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.shared.domain.errors import ValidationError


def test_provider_identity_create() -> None:
    user = User.create("Dimas")
    identity = ProviderIdentity.create(user.id, Provider.TELEGRAM, "12345", username="dimas")
    assert isinstance(identity.id, ProviderIdentityId)
    assert identity.user_id == user.id
    assert identity.provider == Provider.TELEGRAM
    assert identity.provider_user_id == "12345"
    assert identity.username == "dimas"


def test_provider_identity_empty_provider_user_id_raises() -> None:
    user = User.create("Dimas")
    with pytest.raises(ValidationError):
        ProviderIdentity.create(user.id, Provider.TELEGRAM, "   ")


def test_provider_identity_update_username() -> None:
    user = User.create("Dimas")
    identity = ProviderIdentity.create(user.id, Provider.TELEGRAM, "12345")
    before = identity.updated_at
    identity.update_username("new_name")
    assert identity.username == "new_name"
    assert identity.updated_at is not before


def test_provider_identity_equality_by_natural_key() -> None:
    user1 = User.create("A")
    user2 = User.create("B")
    id1 = ProviderIdentity.create(user1.id, Provider.TELEGRAM, "123")
    id2 = ProviderIdentity.create(user2.id, Provider.TELEGRAM, "123")
    assert id1 == id2
    assert id1.id != id2.id
    assert id1.user_id != id2.user_id


def test_provider_identity_inequality_for_different_keys() -> None:
    user = User.create("A")
    id1 = ProviderIdentity.create(user.id, Provider.TELEGRAM, "123")
    id2 = ProviderIdentity.create(user.id, Provider.DISCORD, "123")
    id3 = ProviderIdentity.create(user.id, Provider.TELEGRAM, "456")
    assert id1 != id2
    assert id1 != id3


def test_provider_identity_hash_by_natural_key() -> None:
    user1 = User.create("A")
    user2 = User.create("B")
    id1 = ProviderIdentity.create(user1.id, Provider.TELEGRAM, "123")
    id2 = ProviderIdentity.create(user2.id, Provider.TELEGRAM, "123")
    assert len({id1, id2}) == 1


def test_provider_identity_belongs_to_user() -> None:
    user = User.create("Dimas")
    identity = ProviderIdentity.create(user.id, Provider.TELEGRAM, "12345")
    assert identity.user_id == user.id
