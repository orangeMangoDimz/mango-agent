"""PostgreSQL implementations of identity repository ports."""

from __future__ import annotations

import asyncpg
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError

from mango_agent.modules.identity.domain.ids import ProviderIdentityId
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.identity.ports.repositories import (
    ProviderIdentityRepository,
    UserRepository,
)
from mango_agent.shared.domain.errors import ConflictError, NotFoundError, ValidationError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope


def _user_from_row(row: asyncpg.Record) -> User:
    return User(
        id=UserId.from_string(str(row["id"])),
        display_name=row["display_name"],
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
    )


def _identity_from_row(row: asyncpg.Record) -> ProviderIdentity:
    return ProviderIdentity(
        id=ProviderIdentityId.from_string(str(row["id"])),
        user_id=UserId.from_string(str(row["user_id"])),
        provider=Provider(row["provider"]),
        provider_user_id=row["provider_user_id"],
        username=row["username"],
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
    )


class PostgresUserRepository(UserRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create(self, actor: ActorScope, user: User) -> User:
        try:
            await self._connection.execute(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4)",
                user.id.value,
                user.display_name,
                user.created_at.value,
                user.updated_at.value,
            )
        except UniqueViolationError as exc:
            raise ConflictError("user id already exists") from exc
        return user

    async def get_by_id(self, actor: ActorScope, user_id: UserId) -> User:
        row = await self._connection.fetchrow(
            "SELECT id, display_name, created_at, updated_at FROM users WHERE id = $1",
            user_id.value,
        )
        if row is None:
            raise NotFoundError("user not found")
        return _user_from_row(row)

    async def get_by_provider_identity(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> User:
        row = await self._connection.fetchrow(
            "SELECT u.id, u.display_name, u.created_at, u.updated_at "
            "FROM users u "
            "JOIN provider_identities pi ON pi.user_id = u.id "
            "WHERE pi.provider = $1 AND pi.provider_user_id = $2",
            provider.value,
            provider_user_id,
        )
        if row is None:
            raise NotFoundError("user not found for provider identity")
        return _user_from_row(row)


class PostgresProviderIdentityRepository(ProviderIdentityRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create(self, actor: ActorScope, identity: ProviderIdentity) -> ProviderIdentity:
        try:
            await self._connection.execute(
                "INSERT INTO provider_identities "
                "(id, user_id, provider, provider_user_id, username, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                identity.id.value,
                identity.user_id.value,
                identity.provider.value,
                identity.provider_user_id,
                identity.username,
                identity.created_at.value,
                identity.updated_at.value,
            )
        except UniqueViolationError as exc:
            raise ConflictError("provider identity already exists") from exc
        except ForeignKeyViolationError as exc:
            raise ValidationError("user does not exist") from exc
        return identity

    async def get_by_natural_key(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> ProviderIdentity:
        row = await self._connection.fetchrow(
            "SELECT id, user_id, provider, provider_user_id, username, created_at, updated_at "
            "FROM provider_identities "
            "WHERE provider = $1 AND provider_user_id = $2",
            provider.value,
            provider_user_id,
        )
        if row is None:
            raise NotFoundError("provider identity not found")
        return _identity_from_row(row)
