"""Unit tests for identity repository ports."""

from __future__ import annotations

import pytest

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.identity.ports.repositories import (
    ProviderIdentityRepository,
    UserRepository,
)
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.ports.actor_scope import ActorScope


class FakeProviderIdentityRepository(ProviderIdentityRepository):
    def __init__(self) -> None:
        self._identities: dict[tuple[Provider, str], ProviderIdentity] = {}

    async def create(
        self,
        actor: ActorScope,
        identity: ProviderIdentity,
    ) -> ProviderIdentity:
        self._identities[identity.natural_key()] = identity
        return identity

    async def get_by_natural_key(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> ProviderIdentity:
        key = (provider, provider_user_id)
        identity = self._identities.get(key)
        if identity is None:
            raise NotFoundError(f"identity for {provider.value}/{provider_user_id} not found")
        return identity


class FakeUserRepository(UserRepository):
    def __init__(self, identities: FakeProviderIdentityRepository) -> None:
        self._users: dict[UserId, User] = {}
        self._identities = identities

    async def create(self, actor: ActorScope, user: User) -> User:
        self._users[user.id] = user
        return user

    async def get_by_id(self, actor: ActorScope, user_id: UserId) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        return user

    async def get_by_provider_identity(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> User:
        identity = await self._identities.get_by_natural_key(actor, provider, provider_user_id)
        return await self.get_by_id(actor, identity.user_id)


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(
        user_id=UserId.generate(),
        bot_id="test-bot",
        command="test",
    )


@pytest.fixture
def identities() -> FakeProviderIdentityRepository:
    return FakeProviderIdentityRepository()


@pytest.fixture
def users(identities: FakeProviderIdentityRepository) -> FakeUserRepository:
    return FakeUserRepository(identities)


async def test_create_and_get_user_by_id(
    actor: ActorScope,
    users: FakeUserRepository,
) -> None:
    user = User.create("Alice")
    await users.create(actor, user)
    found = await users.get_by_id(actor, user.id)
    assert found == user


async def test_resolve_user_by_provider_identity(
    actor: ActorScope,
    users: FakeUserRepository,
    identities: FakeProviderIdentityRepository,
) -> None:
    user = User.create("Bob")
    identity = ProviderIdentity.create(user.id, Provider.TELEGRAM, "123", "bob")
    await users.create(actor, user)
    await identities.create(actor, identity)
    found = await users.get_by_provider_identity(actor, Provider.TELEGRAM, "123")
    assert found == user


async def test_get_by_natural_key_returns_identity(
    actor: ActorScope,
    identities: FakeProviderIdentityRepository,
) -> None:
    user_id = UserId.generate()
    identity = ProviderIdentity.create(user_id, Provider.DISCORD, "456", "bob")
    await identities.create(actor, identity)
    found = await identities.get_by_natural_key(actor, Provider.DISCORD, "456")
    assert found == identity
