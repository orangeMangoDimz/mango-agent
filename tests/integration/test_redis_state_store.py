"""Integration tests for Redis conversation-state adapters."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import redis.asyncio

from mango_agent.modules.conversation.adapters.redis_state_store import (
    RedisConfirmationStore,
    RedisConversationStateStore,
    RedisProcessingLock,
    RedisProposalStore,
)
from mango_agent.modules.conversation.domain import (
    ConversationState,
    Message,
    Participant,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.conversation.domain.enums import MessageRole
from mango_agent.modules.conversation.ports import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import OperationId, UserId
from mango_agent.shared.domain.value_objects import Timestamp

pytestmark = pytest.mark.skipif(
    os.environ.get("REDIS_URL") is None,
    reason="REDIS_URL not set; start redis with docker compose up -d redis",
)


@pytest_asyncio.fixture
async def redis_client():
    client = redis.asyncio.from_url(os.environ["REDIS_URL"])
    unique = str(uuid.uuid4())
    try:
        yield client, unique
    finally:
        keys = [key async for key in client.scan_iter(match=f"*test-{unique}*")]
        if keys:
            await client.delete(*keys)
        await client.close()


def _future(seconds: int = 60) -> Timestamp:
    return Timestamp.from_datetime(datetime.now(tz=UTC) + timedelta(seconds=seconds))


def _make_key(
    unique: str,
    bot_id: str | None = None,
    conversation_id: str | None = None,
    user_id: UserId | None = None,
    command: str | None = None,
    provider: Provider = Provider.TELEGRAM,
) -> ConversationKey:
    return ConversationKey(
        provider=provider,
        bot_id=bot_id or f"bot-{unique}",
        conversation_id=conversation_id or f"conv-{unique}",
        user_id=user_id or UserId.generate(),
        command=command or f"test-{unique}",
    )


def _participant(user_id: UserId) -> Participant:
    return Participant(
        user_id=user_id,
        provider=Provider.TELEGRAM,
        provider_user_id="12345",
    )


async def test_state_load_save_clear(redis_client) -> None:
    client, unique = redis_client
    key = _make_key(unique)
    store = RedisConversationStateStore(client)
    state = ConversationState.create(_participant(key.user_id), key.bot_id)

    assert await store.load(key) is None
    assert await store.save(key, state, 0) is True

    loaded = await store.load(key)
    assert loaded is not None
    loaded_state, version = loaded
    assert version == 1
    assert loaded_state == state

    updated = loaded_state.record_message(
        Message(role=MessageRole.USER, content="hello", timestamp=Timestamp.now())
    )
    assert await store.save(key, updated, 1) is True

    reloaded = await store.load(key)
    assert reloaded is not None
    assert reloaded[1] == 2

    await store.clear(key)
    assert await store.load(key) is None


async def test_state_cas_failure(redis_client) -> None:
    client, unique = redis_client
    key = _make_key(unique)
    store = RedisConversationStateStore(client)
    state = ConversationState.create(_participant(key.user_id), key.bot_id)

    assert await store.save(key, state, 0) is True
    assert await store.save(key, state, 0) is False

    updated = state.record_message(
        Message(role=MessageRole.USER, content="hello", timestamp=Timestamp.now())
    )
    assert await store.save(key, updated, 1) is True
    assert await store.save(key, updated, 1) is False


async def test_state_isolation(redis_client) -> None:
    client, unique = redis_client
    store = RedisConversationStateStore(client)

    key_a = _make_key(unique, conversation_id="a")
    key_b = _make_key(unique, conversation_id="b", provider=Provider.DISCORD)
    key_c = _make_key(unique, conversation_id="c", user_id=UserId.generate())

    state_a = ConversationState.create(_participant(key_a.user_id), key_a.bot_id)
    state_b = ConversationState.create(_participant(key_b.user_id), key_b.bot_id)
    state_c = ConversationState.create(_participant(key_c.user_id), key_c.bot_id)

    await store.save(key_a, state_a, 0)
    await store.save(key_b, state_b, 0)
    await store.save(key_c, state_c, 0)

    loaded_a = await store.load(key_a)
    loaded_b = await store.load(key_b)
    loaded_c = await store.load(key_c)

    assert loaded_a is not None and loaded_a[0] == state_a
    assert loaded_b is not None and loaded_b[0] == state_b
    assert loaded_c is not None and loaded_c[0] == state_c


async def test_state_ttl(redis_client) -> None:
    client, unique = redis_client
    key = _make_key(unique)
    store = RedisConversationStateStore(client, ttl_seconds=1)
    state = ConversationState.create(_participant(key.user_id), key.bot_id)

    assert await store.save(key, state, 0) is True
    assert await store.load(key) is not None
    await asyncio.sleep(1.1)
    assert await store.load(key) is None


async def test_proposal_create_get_consume_clear(redis_client) -> None:
    client, unique = redis_client
    key = _make_key(unique)
    store = RedisProposalStore(client)
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Do it", expires_at=_future())

    assert await store.create(key, proposal) == 1

    loaded = await store.get(key)
    assert loaded is not None
    assert loaded[0] == proposal
    assert loaded[1] == 1

    wrong_operation = OperationId.generate()
    assert await store.consume(key, wrong_operation, 1) is False
    assert await store.consume(key, operation_id, 999) is False
    assert await store.consume(key, operation_id, 1) is True

    after = await store.get(key)
    assert after is not None
    assert after[0].consumed is True
    assert after[1] == 2

    assert await store.consume(key, operation_id, 1) is False

    await store.clear(key)
    assert await store.get(key) is None


async def test_confirmation_create_get_consume_clear(redis_client) -> None:
    client, unique = redis_client
    key = _make_key(unique)
    store = RedisConfirmationStore(client)
    operation_id = OperationId.generate()
    confirmation = PendingConfirmation.create(
        operation_id, "delete_task", "task-123", expires_at=_future()
    )

    assert await store.create(key, confirmation) == 1

    loaded = await store.get(key)
    assert loaded is not None
    assert loaded[0] == confirmation
    assert loaded[1] == 1

    wrong_operation = OperationId.generate()
    assert await store.consume(key, wrong_operation, 1) is False
    assert await store.consume(key, operation_id, 999) is False
    assert await store.consume(key, operation_id, 1) is True

    after = await store.get(key)
    assert after is not None
    assert after[0].consumed is True
    assert after[1] == 2

    assert await store.consume(key, operation_id, 1) is False

    await store.clear(key)
    assert await store.get(key) is None


async def test_processing_lock_isolation(redis_client) -> None:
    client, unique = redis_client
    lock_key = f"test-{unique}"
    lock_a = RedisProcessingLock(client, lock_key, ttl_seconds=5)
    lock_b = RedisProcessingLock(client, lock_key, ttl_seconds=5)

    assert await lock_a.acquire() is True
    assert await lock_b.acquire() is False

    assert await lock_a.release() is True
    assert await lock_b.acquire() is True
    assert await lock_b.release() is True
