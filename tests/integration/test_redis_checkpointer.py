"""Integration tests for Redis-backed LangGraph checkpoints."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
import redis.asyncio
from langgraph.checkpoint.base import Checkpoint, empty_checkpoint

from mango_agent.agents.redis_checkpointer import RedisCheckpointSaver
from mango_agent.modules.conversation.ports import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import UserId

pytestmark = pytest.mark.skipif(
    os.environ.get("REDIS_URL") is None,
    reason="REDIS_URL not set; start redis with docker compose up -d redis",
)


@pytest_asyncio.fixture
async def redis_client():
    client = redis.asyncio.from_url(os.environ["REDIS_URL"])
    try:
        yield client
    finally:
        await client.close()


def _conversation_key(unique: str, *, user_id: UserId | None = None) -> ConversationKey:
    return ConversationKey(
        provider=Provider.TELEGRAM,
        bot_id=f"bot-{unique}",
        conversation_id=f"conversation-{unique}",
        thread_id=f"thread-{unique}",
        user_id=user_id or UserId.generate(),
        command="task_management",
    )


def _config(saver: RedisCheckpointSaver, checkpoint_id: str | None = None) -> dict[str, Any]:
    configurable: dict[str, str] = {
        "thread_id": saver.thread_id,
        "checkpoint_ns": "",
    }
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


def _checkpoint(checkpoint_id: str, *, value: Any, version: int = 1) -> Checkpoint:
    checkpoint = empty_checkpoint()
    checkpoint["id"] = checkpoint_id
    checkpoint["channel_values"] = {"value": value}
    checkpoint["channel_versions"] = {"value": version}
    return checkpoint


async def test_checkpoint_round_trip_isolated_by_conversation_scope(redis_client) -> None:
    unique = str(uuid.uuid4())
    first = RedisCheckpointSaver(redis_client, _conversation_key(unique))
    second = RedisCheckpointSaver(redis_client, _conversation_key(unique))
    first_checkpoint = _checkpoint("0001", value={"bytes": b"safe"})
    second_checkpoint = _checkpoint("0001", value={"title": "other"})
    try:
        await first.aput(_config(first), first_checkpoint, {"step": 1}, {"value": 1})
        await second.aput(_config(second), second_checkpoint, {"step": 1}, {"value": 1})

        first_loaded = await first.aget_tuple(_config(first))
        second_loaded = await second.aget_tuple(_config(second))

        assert first_loaded is not None
        assert second_loaded is not None
        assert first_loaded.checkpoint["channel_values"] == {"value": {"bytes": b"safe"}}
        assert second_loaded.checkpoint["channel_values"] == {"value": {"title": "other"}}

        await first.adelete_thread(first.thread_id)
        assert await first.aget_tuple(_config(first)) is None
        assert await second.aget_tuple(_config(second)) is not None
    finally:
        await first.adelete_thread(first.thread_id)
        await second.adelete_thread(second.thread_id)


async def test_checkpoint_ttl_expires_the_scoped_thread(redis_client) -> None:
    saver = RedisCheckpointSaver(redis_client, _conversation_key(str(uuid.uuid4())), ttl_seconds=1)
    checkpoint = _checkpoint("0001", value="temporary")
    try:
        await saver.aput(_config(saver), checkpoint, {}, {"value": 1})
        assert await saver.aget_tuple(_config(saver)) is not None

        await asyncio.sleep(1.1)

        assert await saver.aget_tuple(_config(saver)) is None
    finally:
        await saver.adelete_thread(saver.thread_id)
