"""PostgreSQL Unit of Work adapter."""

from __future__ import annotations

from types import TracebackType
from typing import final

import asyncpg

from mango_agent.modules.attachments.adapters.postgres_repositories import (
    PostgresAttachmentRepository,
)
from mango_agent.modules.identity.adapters.postgres_repositories import (
    PostgresProviderIdentityRepository,
    PostgresUserRepository,
)
from mango_agent.modules.task_management.adapters.postgres_repositories import (
    PostgresProjectRepository,
    PostgresTaskRepository,
)
from mango_agent.shared.adapters.postgres.idempotency import PostgresIdempotencyRepository
from mango_agent.shared.infrastructure.postgres.connection import PostgresConnectionPool
from mango_agent.shared.ports.unit_of_work import UnitOfWork


@final
class PostgresUnitOfWork(UnitOfWork):
    """Atomic transaction boundary backed by a Postgres connection."""

    def __init__(self, pool: PostgresConnectionPool) -> None:
        self._pool = pool
        self._connection: asyncpg.Connection | None = None
        self._transaction: asyncpg.transaction.Transaction | None = None
        self.users: PostgresUserRepository | None = None
        self.provider_identities: PostgresProviderIdentityRepository | None = None
        self.projects: PostgresProjectRepository | None = None
        self.tasks: PostgresTaskRepository | None = None
        self.attachments: PostgresAttachmentRepository | None = None
        self.idempotency: PostgresIdempotencyRepository | None = None

    async def begin(self) -> None:
        self._connection = await self._pool.acquire()
        self._transaction = self._connection.transaction()
        await self._transaction.start()
        self._init_repositories()

    async def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("no active transaction")
        await self._transaction.commit()
        await self._release()

    async def rollback(self) -> None:
        if self._transaction is None:
            raise RuntimeError("no active transaction")
        await self._transaction.rollback()
        await self._release()

    async def _release(self) -> None:
        if self._connection is not None:
            self._pool.release(self._connection)
            self._connection = None
        self._transaction = None
        self._clear_repositories()

    def _init_repositories(self) -> None:
        assert self._connection is not None
        self.users = PostgresUserRepository(self._connection)
        self.provider_identities = PostgresProviderIdentityRepository(self._connection)
        self.projects = PostgresProjectRepository(self._connection)
        self.tasks = PostgresTaskRepository(self._connection)
        self.attachments = PostgresAttachmentRepository(self._connection)
        self.idempotency = PostgresIdempotencyRepository(self._connection)

    def _clear_repositories(self) -> None:
        self.users = None
        self.provider_identities = None
        self.projects = None
        self.tasks = None
        self.attachments = None
        self.idempotency = None

    async def __aenter__(self) -> PostgresUnitOfWork:
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            await self.commit()
        else:
            await self.rollback()
