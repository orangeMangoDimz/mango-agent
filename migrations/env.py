"""Alembic environment for async PostgreSQL migrations."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from mango_agent.shared.infrastructure.config import PostgresConfig

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _db_url() -> str:
    url = PostgresConfig().database_url.get_secret_value()
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg" + url[len("postgresql") :]
    return url


config.set_main_option("sqlalchemy.url", _db_url())

target_metadata = None


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool, future=True)
    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
