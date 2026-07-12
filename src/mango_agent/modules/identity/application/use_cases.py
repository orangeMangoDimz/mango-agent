"""Identity application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, final

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.identity.ports.repositories import (
    ProviderIdentityRepository,
    UserRepository,
    UserSearchQuery,
)
from mango_agent.shared.domain.errors import (
    InternalError,
    MangoError,
    NotFoundError,
)
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import (
    MAX_LIMIT,
    PaginatedResult,
    Pagination,
)
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.unit_of_work import UnitOfWorkFactory

__all__ = [
    "AuthenticatedContext",
    "GetUser",
    "ResolveProviderIdentity",
    "SearchKnownUsers",
]


@final
@dataclass(frozen=True, slots=True)
class AuthenticatedContext:
    """Immutable execution context produced by resolving a provider identity."""

    internal_user_id: UserId
    bot_id: str
    command: str
    provider: Provider
    provider_user_id: str


class IdentityUnitOfWork(Protocol):
    """Unit of work exposing identity repositories."""

    users: UserRepository
    provider_identities: ProviderIdentityRepository

    async def begin(self) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


def _as_identity_uow(uow: UnitOfWorkFactory) -> IdentityUnitOfWork:
    """Return a unit of work exposing identity repositories."""
    created = uow()
    if not hasattr(created, "users") or not hasattr(created, "provider_identities"):
        raise TypeError("unit of work does not expose identity repositories")
    return created


class ResolveProviderIdentity:
    """Resolve a provider-authenticated identity to an internal user.

    The provider identity is the source of truth. On first encounter a new
    internal user is created; on subsequent encounters the existing internal
    user linked to that provider identity is returned. The caller's
    ``actor.user_id`` is used only for repository authorization scaffolding and
    is not treated as the authoritative internal user id.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
        username: str | None,
        display_name: str,
    ) -> Result[AuthenticatedContext, MangoError]:
        uow = _as_identity_uow(self._uow_factory)
        try:
            await uow.begin()
            try:
                identity = await uow.provider_identities.get_by_natural_key(
                    actor, provider, provider_user_id
                )
            except NotFoundError:
                user = User.create(display_name.strip())
                identity = ProviderIdentity.create(user.id, provider, provider_user_id, username)
                await uow.users.create(actor, user)
                await uow.provider_identities.create(actor, identity)
            else:
                user = await uow.users.get_by_id(
                    ActorScope(
                        user_id=identity.user_id,
                        bot_id=actor.bot_id,
                        command=actor.command,
                    ),
                    identity.user_id,
                )
            await uow.commit()
            return Result.success(
                AuthenticatedContext(
                    internal_user_id=user.id,
                    bot_id=actor.bot_id,
                    command=actor.command or "",
                    provider=provider,
                    provider_user_id=provider_user_id,
                )
            )
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)
        except Exception as exc:
            await uow.rollback()
            return Result.failure(InternalError(str(exc)))


class GetUser:
    """Load a user by id. Actor may read themselves or any known user."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, actor: ActorScope, user_id: UserId) -> Result[User, MangoError]:
        uow = _as_identity_uow(self._uow_factory)
        try:
            await uow.begin()
            # Actor may read themselves or any known user.
            result = await uow.users.search(
                actor, UserSearchQuery(), Pagination(limit=MAX_LIMIT, offset=0)
            )
            user = next((u for u in result.items if u.id == user_id), None)
            if user is None:
                await uow.rollback()
                return Result.failure(NotFoundError(f"user {user_id} not found"))
            await uow.commit()
            return Result.success(user)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)
        except Exception as exc:
            await uow.rollback()
            return Result.failure(InternalError(str(exc)))


class SearchKnownUsers:
    """Search users by display name substring or list all known users."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        actor: ActorScope,
        display_name_contains: str | None = None,
        pagination: Pagination | None = None,
    ) -> Result[PaginatedResult[User], MangoError]:
        uow = _as_identity_uow(self._uow_factory)
        try:
            await uow.begin()
            result = await uow.users.search(
                actor,
                UserSearchQuery(display_name_contains=display_name_contains),
                pagination or Pagination.default(),
            )
            await uow.commit()
            return Result.success(result)
        except MangoError as exc:
            await uow.rollback()
            return Result.failure(exc)
        except Exception as exc:
            await uow.rollback()
            return Result.failure(InternalError(str(exc)))
