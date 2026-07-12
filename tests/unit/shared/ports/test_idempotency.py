"""Unit tests for the IdempotencyRepository port."""

from __future__ import annotations

import pytest

from mango_agent.shared.domain.ids import OperationId, UserId
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository


class FakeIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._operations: dict[IdempotencyKey, OperationId] = {}

    async def claim_event(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        return self._operations.get(key)

    async def record_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> None:
        self._operations[key] = operation_id

    async def lookup_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        return self._operations.get(key)


@pytest.fixture
def actor() -> ActorScope:
    return ActorScope(
        user_id=UserId.generate(),
        bot_id="test-bot",
        command="test",
    )


@pytest.fixture
def repo() -> FakeIdempotencyRepository:
    return FakeIdempotencyRepository()


async def test_claim_event_returns_none_for_new_key(
    actor: ActorScope,
    repo: FakeIdempotencyRepository,
) -> None:
    key = IdempotencyKey("event", "123")
    assert await repo.claim_event(actor, key) is None


async def test_record_and_lookup_operation(
    actor: ActorScope,
    repo: FakeIdempotencyRepository,
) -> None:
    key = IdempotencyKey("operation", "456")
    operation_id = OperationId.generate()
    await repo.record_operation(actor, key, operation_id)
    assert await repo.lookup_operation(actor, key) == operation_id
    assert await repo.claim_event(actor, key) == operation_id


def test_idempotency_key_for_provider_event() -> None:
    key = IdempotencyKey.for_provider_event("telegram", "evt-1")
    assert key.scope == "provider_event:telegram"
    assert key.external_id == "evt-1"
