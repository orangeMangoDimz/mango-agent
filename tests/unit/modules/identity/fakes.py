"""In-memory fake repositories for identity unit tests."""

from __future__ import annotations

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.identity.ports.repositories import (
    ProviderIdentityRepository,
    UserRepository,
    UserSearchQuery,
)
from mango_agent.shared.domain.errors import ConflictError, NotFoundError, UnauthorizedError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.unit_of_work import UnitOfWork


class FakeProviderIdentityRepository(ProviderIdentityRepository):
    """In-memory provider identity repository."""

    def __init__(self) -> None:
        self._identities: dict[tuple[Provider, str], ProviderIdentity] = {}

    async def create(self, actor: ActorScope, identity: ProviderIdentity) -> ProviderIdentity:
        if identity.natural_key() in self._identities:
            raise ConflictError("provider identity already exists")
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
            raise NotFoundError(
                f"provider identity for {provider.value}/{provider_user_id} not found"
            )
        return identity


class FakeUserRepository(UserRepository):
    """In-memory user repository with actor scoping on direct reads."""

    def __init__(self, identities: FakeProviderIdentityRepository | None = None) -> None:
        self._users: dict[UserId, User] = {}
        self._identities = identities or FakeProviderIdentityRepository()

    async def create(self, actor: ActorScope, user: User) -> User:
        if user.id in self._users:
            raise ConflictError("user already exists")
        self._users[user.id] = user
        return user

    async def get_by_id(self, actor: ActorScope, user_id: UserId) -> User:
        user = self._users.get(user_id)
        if user is None or user.id != actor.user_id:
            raise NotFoundError(f"user {user_id} not found")
        return user

    async def get_by_provider_identity(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> User:
        identity = await self._identities.get_by_natural_key(actor, provider, provider_user_id)
        if identity.user_id != actor.user_id:
            raise UnauthorizedError("provider identity belongs to another user")
        return await self.get_by_id(actor, identity.user_id)

    async def search(
        self,
        actor: ActorScope,
        query: UserSearchQuery,
        pagination: Pagination,
    ) -> PaginatedResult[User]:
        search_term = query.display_name_contains
        if search_term is None:
            matches = list(self._users.values())
        else:
            term = search_term.lower()
            matches = [user for user in self._users.values() if term in user.display_name.lower()]
        total = len(matches)
        page = matches[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(
            items=tuple(page),
            total=total,
            pagination=pagination,
        )


class FakeIdentityUnitOfWork(UnitOfWork):
    """In-memory unit of work for identity use cases."""

    def __init__(self) -> None:
        self.provider_identities = FakeProviderIdentityRepository()
        self.users = FakeUserRepository(self.provider_identities)
        self.begun = False
        self.committed = False
        self.rolled_back = False

    async def begin(self) -> None:
        self.begun = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
