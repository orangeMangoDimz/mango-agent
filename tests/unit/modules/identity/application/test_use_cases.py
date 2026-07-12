"""Unit tests for identity application use cases."""

from __future__ import annotations

import typing

import pytest

from mango_agent.modules.identity.application.use_cases import (
    GetUser,
    ResolveProviderIdentity,
    SearchKnownUsers,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.identity.ports.repositories import UserSearchQuery
from mango_agent.shared.domain.errors import NotFoundError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Pagination
from mango_agent.shared.ports.actor_scope import ActorScope
from tests.unit.modules.identity.fakes import FakeIdentityUnitOfWork


@pytest.fixture
def uow() -> FakeIdentityUnitOfWork:
    return FakeIdentityUnitOfWork()


@pytest.fixture
def uow_factory(
    uow: FakeIdentityUnitOfWork,
) -> typing.Callable[[], FakeIdentityUnitOfWork]:
    return lambda: uow


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(
        user_id=UserId.generate(),
        bot_id="test-bot",
        command="test-cmd",
    )


async def test_resolve_creates_new_user_and_identity_on_first_encounter(
    uow: FakeIdentityUnitOfWork,
    uow_factory: typing.Callable[[], FakeIdentityUnitOfWork],
    actor: ActorScope,
) -> None:
    resolve = ResolveProviderIdentity(uow_factory=uow_factory)

    result = await resolve(
        actor,
        Provider.TELEGRAM,
        "telegram-123",
        "alice",
        "Alice",
    )

    assert result.is_success
    context = result.value
    assert context.internal_user_id is not None
    assert context.bot_id == "test-bot"
    assert context.command == "test-cmd"
    assert context.provider == Provider.TELEGRAM
    assert context.provider_user_id == "telegram-123"

    user_actor = ActorScope(
        user_id=context.internal_user_id,
        bot_id="test-bot",
        command="test-cmd",
    )
    user = await uow.users.get_by_id(user_actor, context.internal_user_id)
    assert user.display_name == "Alice"

    identity = await uow.provider_identities.get_by_natural_key(
        actor, Provider.TELEGRAM, "telegram-123"
    )
    assert identity.user_id == context.internal_user_id
    assert identity.username == "alice"
    assert uow.committed


async def test_resolve_returns_existing_user_and_does_not_duplicate(
    uow: FakeIdentityUnitOfWork,
    uow_factory: typing.Callable[[], FakeIdentityUnitOfWork],
    actor: ActorScope,
) -> None:
    resolve = ResolveProviderIdentity(uow_factory=uow_factory)

    first = await resolve(
        actor,
        Provider.TELEGRAM,
        "telegram-123",
        "alice",
        "Alice",
    )
    assert first.is_success

    second = await resolve(
        actor,
        Provider.TELEGRAM,
        "telegram-123",
        "alice",
        "Alice",
    )
    assert second.is_success
    assert second.value.internal_user_id == first.value.internal_user_id

    search_result = await uow.users.search(actor, UserSearchQuery(), Pagination.default())
    assert search_result.total == 1


async def test_resolve_returns_same_internal_user_for_separate_provider_sessions(
    uow: FakeIdentityUnitOfWork,
    uow_factory: typing.Callable[[], FakeIdentityUnitOfWork],
) -> None:
    actor_a = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    actor_b = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")

    resolve = ResolveProviderIdentity(uow_factory=uow_factory)
    first = await resolve(actor_a, Provider.TELEGRAM, "telegram-123", "alice", "Alice")
    second = await resolve(actor_b, Provider.TELEGRAM, "telegram-123", "alice", "Alice")

    assert first.is_success
    assert second.is_success
    assert first.value.internal_user_id == second.value.internal_user_id
    assert uow.committed


async def test_get_user_for_self_and_other_known_user(
    uow: FakeIdentityUnitOfWork,
    uow_factory: typing.Callable[[], FakeIdentityUnitOfWork],
) -> None:
    actor_a = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    actor_b = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    user_a = User.create("Alice")
    user_b = User.create("Bob")
    await uow.users.create(actor_a, user_a)
    await uow.users.create(actor_b, user_b)

    get_user = GetUser(uow_factory=uow_factory)

    self_result = await get_user(actor_a, user_a.id)
    assert self_result.is_success
    assert self_result.value.id == user_a.id

    other_result = await get_user(actor_a, user_b.id)
    assert other_result.is_success
    assert other_result.value.id == user_b.id


async def test_search_known_users_filtering(
    uow: FakeIdentityUnitOfWork,
    uow_factory: typing.Callable[[], FakeIdentityUnitOfWork],
) -> None:
    actor = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    users = [User.create("Alice"), User.create("Bob"), User.create("Charlie")]
    for user in users:
        await uow.users.create(actor, user)

    search = SearchKnownUsers(uow_factory=uow_factory)

    all_result = await search(actor, None)
    assert all_result.is_success
    assert all_result.value.total == 3

    filtered = await search(actor, "li")
    assert filtered.is_success
    assert filtered.value.total == 2
    names = {u.display_name for u in filtered.value.items}
    assert names == {"Alice", "Charlie"}


async def test_cross_user_get_by_id_is_rejected(
    uow: FakeIdentityUnitOfWork,
) -> None:
    actor_a = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    actor_b = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")
    user_b = User.create("Bob")
    await uow.users.create(actor_b, user_b)

    with pytest.raises(NotFoundError):
        await uow.users.get_by_id(actor_a, user_b.id)
