"""AsyncPG connection pool for PostgreSQL adapters."""

from __future__ import annotations

import asyncpg


class PostgresConnectionPool:
    """A thin wrapper around asyncpg's connection pool."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def acquire(self) -> asyncpg.Connection:
        if self._pool is None:
            raise RuntimeError("pool is not connected")
        return await self._pool.acquire()

    def release(self, connection: asyncpg.Connection) -> None:
        if self._pool is not None:
            self._pool.release(connection)

    async def __aenter__(self) -> PostgresConnectionPool:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()
