"""Unit tests for the scoped Redis LangGraph checkpoint saver."""

from __future__ import annotations

import fnmatch
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, TypedDict

import pytest
from langgraph.checkpoint.base import Checkpoint, empty_checkpoint
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from redis.exceptions import ConnectionError as RedisConnectionError

from mango_agent.agents.redis_checkpointer import (
    CheckpointCorruptionError,
    CheckpointPersistenceError,
    CheckpointScopeError,
    RedisCheckpointSaver,
)
from mango_agent.modules.conversation.ports import ConversationKey
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import UserId


@dataclass
class _StoredValue:
    value: str
    ttl: int | None


class FakeAsyncRedis:
    """Small Redis double covering this adapter's value/key operations."""

    def __init__(self) -> None:
        self.values: dict[str, _StoredValue] = {}
        self.fail = False
        self._counter = 0

    def _check_available(self) -> None:
        if self.fail:
            raise RedisConnectionError("unavailable")

    async def get(self, key: str) -> str | None:
        self._check_available()
        value = self.values.get(key)
        return value.value if value else None

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        self._check_available()
        if nx and key in self.values:
            return False
        self.values[key] = _StoredValue(value=value, ttl=ex)
        return True

    async def incr(self, key: str) -> int:
        self._check_available()
        self._counter += 1
        self.values[key] = _StoredValue(value=str(self._counter), ttl=None)
        return self._counter

    async def expire(self, key: str, ttl: int) -> bool:
        self._check_available()
        value = self.values.get(key)
        if value is None:
            return False
        value.ttl = ttl
        return True

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        self._check_available()
        for key in tuple(self.values):
            if fnmatch.fnmatch(key, match):
                yield key

    async def delete(self, *keys: str) -> int:
        self._check_available()
        deleted = 0
        for key in keys:
            if self.values.pop(key, None) is not None:
                deleted += 1
        return deleted


class _ApprovalState(TypedDict, total=False):
    approval: str


def _await_approval(_: _ApprovalState) -> dict[str, str]:
    return {"approval": str(interrupt("Approve the task?"))}


def _conversation_key(*, user_id: UserId | None = None) -> ConversationKey:
    return ConversationKey(
        provider=Provider.TELEGRAM,
        bot_id="bot-1",
        conversation_id="conversation-1",
        user_id=user_id or UserId.generate(),
        command="task_management",
    )


def _config(saver: RedisCheckpointSaver, checkpoint_id: str | None = None) -> dict[str, Any]:
    configurable: dict[str, str] = {
        "thread_id": saver.thread_id,
        "checkpoint_ns": "",
    }
    if checkpoint_id:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


def _checkpoint(
    checkpoint_id: str,
    *,
    values: dict[str, Any],
    versions: dict[str, int],
) -> Checkpoint:
    checkpoint = empty_checkpoint()
    checkpoint["id"] = checkpoint_id
    checkpoint["channel_values"] = values
    checkpoint["channel_versions"] = versions
    return checkpoint


async def test_round_trip_reconstructs_channel_values_and_pending_writes() -> None:
    redis = FakeAsyncRedis()
    saver = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    first = _checkpoint("0001", values={"input": {"title": "One"}}, versions={"input": 1})

    first_config = await saver.aput(_config(saver), first, {"step": -1}, {"input": 1})
    await saver.aput_writes(first_config, [("input", {"title": "One"})], "task-1")
    second = _checkpoint("0002", values={"result": ["ok"]}, versions={"input": 1, "result": 1})
    second_config = await saver.aput(first_config, second, {"step": 0}, {"result": 1})
    await saver.aput_writes(second_config, [("result", ["ok"])], "task-2")

    loaded = await saver.aget_tuple(_config(saver))

    assert loaded is not None
    assert loaded.config == second_config
    assert loaded.checkpoint["channel_values"] == {"input": {"title": "One"}, "result": ["ok"]}
    assert loaded.metadata == {"step": 0}
    assert loaded.parent_config == first_config
    assert loaded.pending_writes == [("task-2", "result", ["ok"])]
    assert all(value.ttl == 24 * 60 * 60 for value in redis.values.values())


async def test_normal_pending_writes_are_idempotent_and_special_writes_replace() -> None:
    redis = FakeAsyncRedis()
    saver = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    checkpoint = _checkpoint("0001", values={"input": "one"}, versions={"input": 1})
    config = await saver.aput(_config(saver), checkpoint, {}, {"input": 1})

    await saver.aput_writes(config, [("input", "first")], "task-1")
    await saver.aput_writes(config, [("input", "second")], "task-1")
    await saver.aput_writes(config, [("__error__", "first")], "task-1")
    await saver.aput_writes(config, [("__error__", "second")], "task-1")

    loaded = await saver.aget_tuple(config)

    assert loaded is not None
    assert loaded.pending_writes is not None
    assert ("task-1", "input", "first") in loaded.pending_writes
    assert ("task-1", "__error__", "second") in loaded.pending_writes


async def test_scope_rejects_another_conversation_and_deletion_is_scoped() -> None:
    redis = FakeAsyncRedis()
    first = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    second = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    checkpoint = _checkpoint("0001", values={"input": "one"}, versions={"input": 1})
    await first.aput(_config(first), checkpoint, {}, {"input": 1})

    with pytest.raises(CheckpointScopeError):
        await first.aget_tuple(_config(second))
    with pytest.raises(CheckpointScopeError):
        await first.adelete_thread(second.thread_id)

    assert await first.aget_tuple(_config(first)) is not None
    await first.adelete_thread(first.thread_id)
    assert await first.aget_tuple(_config(first)) is None


async def test_lists_metadata_filters_and_before_checkpoint() -> None:
    redis = FakeAsyncRedis()
    saver = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    first = _checkpoint("0001", values={"input": "one"}, versions={"input": 1})
    first_config = await saver.aput(_config(saver), first, {"source": "input"}, {"input": 1})
    second = _checkpoint("0002", values={"result": "two"}, versions={"input": 1, "result": 1})
    second_config = await saver.aput(first_config, second, {"source": "loop"}, {"result": 1})

    matching = [item async for item in saver.alist(_config(saver), filter={"source": "loop"})]
    before = [item async for item in saver.alist(_config(saver), before=second_config)]

    assert [item.config["configurable"]["checkpoint_id"] for item in matching] == ["0002"]
    assert [item.config["configurable"]["checkpoint_id"] for item in before] == ["0001"]


async def test_restart_resumes_a_langgraph_interrupt() -> None:
    redis = FakeAsyncRedis()
    conversation_key = _conversation_key()
    saver = RedisCheckpointSaver(redis, conversation_key)  # type: ignore[arg-type]
    builder = StateGraph(_ApprovalState)
    builder.add_node("await_approval", _await_approval)
    builder.add_edge(START, "await_approval")
    builder.add_edge("await_approval", END)
    graph = builder.compile(checkpointer=saver)

    paused = await graph.ainvoke({}, _config(saver))

    assert "__interrupt__" in paused

    restarted_saver = RedisCheckpointSaver(redis, conversation_key)  # type: ignore[arg-type]
    restarted_graph = builder.compile(checkpointer=restarted_saver)
    resumed = await restarted_graph.ainvoke(
        Command(resume="approved"),
        _config(restarted_saver),
    )

    assert resumed == {"approval": "approved"}


async def test_corruption_and_redis_failures_are_explicit() -> None:
    redis = FakeAsyncRedis()
    saver = RedisCheckpointSaver(redis, _conversation_key())  # type: ignore[arg-type]
    checkpoint = _checkpoint("0001", values={"input": "one"}, versions={"input": 1})
    await saver.aput(_config(saver), checkpoint, {}, {"input": 1})
    checkpoint_key = saver._checkpoint_key("", "0001")
    redis.values[checkpoint_key] = _StoredValue(value="not-json", ttl=1)

    with pytest.raises(CheckpointCorruptionError):
        await saver.aget_tuple(_config(saver, "0001"))

    redis.fail = True
    with pytest.raises(CheckpointPersistenceError):
        await saver.aget_tuple(_config(saver))
