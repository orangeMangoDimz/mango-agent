"""PostgreSQL implementation of the idempotency repository port."""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError

from mango_agent.shared.domain.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from mango_agent.shared.domain.ids import OperationId
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository


class PostgresIdempotencyRepository(IdempotencyRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    def _provider(self, key: IdempotencyKey) -> str:
        return key.scope.removeprefix("provider_event:")

    async def claim_event(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        try:
            row = await self._connection.fetchrow(
                "INSERT INTO idempotency_records "
                "(id, user_id, provider, bot_instance, operation_key, operation_type, "
                "status, result_resource_id, created_at, completed_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, 'claimed', NULL, $7, NULL) "
                "ON CONFLICT (provider, bot_instance, operation_key) DO NOTHING "
                "RETURNING id",
                OperationId.generate().value,
                actor.user_id.value,
                self._provider(key),
                actor.bot_id,
                key.external_id,
                actor.command,
                datetime.now(tz=UTC),
            )
        except UniqueViolationError as exc:
            raise ConflictError("idempotency key already claimed") from exc
        except ForeignKeyViolationError as exc:
            raise ValidationError("user does not exist") from exc

        if row is not None:
            return None

        existing = await self._connection.fetchrow(
            "SELECT status, result_resource_id FROM idempotency_records "
            "WHERE provider = $1 AND bot_instance = $2 AND operation_key = $3",
            self._provider(key),
            actor.bot_id,
            key.external_id,
        )
        if existing is None or existing["result_resource_id"] is None:
            return None
        return OperationId.from_string(str(existing["result_resource_id"]))

    async def record_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> None:
        result = await self._connection.execute(
            "UPDATE idempotency_records "
            "SET status = 'completed', result_resource_id = $1, completed_at = $2 "
            "WHERE provider = $3 AND bot_instance = $4 AND operation_key = $5",
            operation_id.value,
            datetime.now(tz=UTC),
            self._provider(key),
            actor.bot_id,
            key.external_id,
        )
        if result == "UPDATE 0":
            raise NotFoundError("idempotency record not found")

    async def lookup_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        row = await self._connection.fetchrow(
            "SELECT result_resource_id FROM idempotency_records "
            "WHERE provider = $1 AND bot_instance = $2 "
            "AND operation_key = $3 AND status = 'completed'",
            self._provider(key),
            actor.bot_id,
            key.external_id,
        )
        if row is None or row["result_resource_id"] is None:
            return None
        return OperationId.from_string(str(row["result_resource_id"]))
