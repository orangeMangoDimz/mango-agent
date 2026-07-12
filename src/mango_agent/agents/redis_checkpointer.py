"""Scoped Redis persistence for LangGraph checkpoints.

The saver is intentionally bound to one ``ConversationKey``.  LangGraph only
receives the derived thread ID, while this adapter independently verifies that
every checkpoint operation stays within that authenticated conversation scope.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any, Final, cast, final

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from redis.asyncio import Redis
from redis.exceptions import RedisError

from mango_agent.modules.conversation.ports import ConversationKey

__all__ = [
    "CheckpointCorruptionError",
    "CheckpointPersistenceError",
    "CheckpointScopeError",
    "RedisCheckpointSaver",
]

DEFAULT_CHECKPOINT_TTL_SECONDS: Final = 24 * 60 * 60
_KEY_PREFIX: Final = "mango:langgraph:checkpoint:v1"
_SCHEMA_VERSION: Final = 1
_CHECKPOINT_SEGMENT: Final = "checkpoint"
_BLOB_SEGMENT: Final = "blob"
_WRITE_SEGMENT: Final = "write"
_WRITE_ORDER_SEGMENT: Final = "write-order"
_SERDE_TYPE_KEY: Final = "type"
_SERDE_DATA_KEY: Final = "data"
_SERDE_TYPES: Final = frozenset({"null", "bytes", "bytearray", "json", "msgpack"})
_REDIS_UNAVAILABLE_MESSAGE: Final = "Redis is unavailable for workflow checkpoints"


class CheckpointPersistenceError(RuntimeError):
    """Raised when Redis checkpoint persistence cannot safely continue."""


@final
class CheckpointScopeError(CheckpointPersistenceError):
    """Raised when a LangGraph config is outside this saver conversation scope."""


@final
class CheckpointCorruptionError(CheckpointPersistenceError):
    """Raised when a Redis checkpoint record is malformed or unsafe to decode."""


def _decode_redis_value(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _key_part(value: str | int | float) -> str:
    """Return a delimiter-safe key segment that preserves JSON scalar types."""

    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _thread_digest(thread_id: str) -> str:
    return hashlib.sha256(thread_id.encode("utf-8")).hexdigest()


@final
class RedisCheckpointSaver(BaseCheckpointSaver[str]):
    """Async LangGraph checkpointer isolated to one authenticated conversation.

    Checkpoint records, channel blobs, and pending writes have individual Redis
    keys.  That avoids a read-modify-write document race between ``aput`` and
    ``aput_writes`` while retaining a JSON/base64-only at-rest representation.
    """

    def __init__(
        self,
        redis: Redis,
        conversation_key: ConversationKey,
        *,
        ttl_seconds: int = DEFAULT_CHECKPOINT_TTL_SECONDS,
        serde: SerializerProtocol | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("checkpoint ttl_seconds must be greater than zero")

        # Pickle is deliberately disabled.  The graph state must be serializable
        # through LangGraph's JSON/msgpack serializer, not arbitrary Python code.
        safe_serde = serde or JsonPlusSerializer(
            pickle_fallback=False,
            allowed_json_modules=None,
            allowed_msgpack_modules=None,
        )
        super().__init__(serde=safe_serde)
        self._redis = redis
        self._ttl_seconds = ttl_seconds
        self._conversation_key = conversation_key
        self._thread_id = self.thread_id_for(conversation_key)
        self._key_prefix = f"{_KEY_PREFIX}:{_thread_digest(self._thread_id)}"

    @staticmethod
    def thread_id_for(conversation_key: ConversationKey) -> str:
        """Derive the sole LangGraph thread ID allowed by this saver."""

        return str(conversation_key)

    @property
    def thread_id(self) -> str:
        """Return the derived thread ID for graph invocation configuration."""

        return self._thread_id

    def _checkpoint_key(self, checkpoint_ns: str, checkpoint_id: str) -> str:
        return (
            f"{self._key_prefix}:{_CHECKPOINT_SEGMENT}:"
            f"{_key_part(checkpoint_ns)}:{_key_part(checkpoint_id)}"
        )

    def _checkpoint_scan_pattern(self) -> str:
        return f"{self._key_prefix}:{_CHECKPOINT_SEGMENT}:*"

    def _blob_key(
        self,
        checkpoint_ns: str,
        channel: str,
        version: str | int | float,
    ) -> str:
        return (
            f"{self._key_prefix}:{_BLOB_SEGMENT}:"
            f"{_key_part(checkpoint_ns)}:{_key_part(channel)}:{_key_part(version)}"
        )

    def _write_key(
        self,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        write_index: int,
    ) -> str:
        return (
            f"{self._key_prefix}:{_WRITE_SEGMENT}:"
            f"{_key_part(checkpoint_ns)}:{_key_part(checkpoint_id)}:"
            f"{_key_part(task_id)}:{write_index}"
        )

    def _write_scan_pattern(self, checkpoint_ns: str, checkpoint_id: str) -> str:
        return (
            f"{self._key_prefix}:{_WRITE_SEGMENT}:"
            f"{_key_part(checkpoint_ns)}:{_key_part(checkpoint_id)}:*"
        )

    def _write_order_key(self) -> str:
        return f"{self._key_prefix}:{_WRITE_ORDER_SEGMENT}"

    def _encode_payload(self, value: Any) -> dict[str, str]:
        try:
            value_type, value_bytes = self.serde.dumps_typed(value)
        except Exception as exc:
            raise CheckpointPersistenceError("checkpoint state is not safely serializable") from exc
        if value_type not in _SERDE_TYPES:
            raise CheckpointPersistenceError(
                f"checkpoint serializer returned unsupported type: {value_type!r}"
            )
        return {
            _SERDE_TYPE_KEY: value_type,
            _SERDE_DATA_KEY: base64.b64encode(value_bytes).decode("ascii"),
        }

    def _decode_payload(self, value: object) -> Any:
        if not isinstance(value, dict):
            raise CheckpointCorruptionError("checkpoint payload must be an object")
        value_type = value.get(_SERDE_TYPE_KEY)
        encoded = value.get(_SERDE_DATA_KEY)
        if not isinstance(value_type, str) or value_type not in _SERDE_TYPES:
            raise CheckpointCorruptionError("checkpoint payload type is invalid")
        if not isinstance(encoded, str):
            raise CheckpointCorruptionError("checkpoint payload data is invalid")
        try:
            data = base64.b64decode(encoded, validate=True)
            return self.serde.loads_typed((value_type, data))
        except (binascii.Error, ValueError, TypeError, NotImplementedError) as exc:
            raise CheckpointCorruptionError("checkpoint payload cannot be decoded") from exc
        except Exception as exc:
            raise CheckpointCorruptionError("checkpoint payload is unsafe to decode") from exc

    @staticmethod
    def _dump_record(record: dict[str, object]) -> str:
        return json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _load_record(raw: bytes | str) -> dict[str, object]:
        try:
            value = json.loads(_decode_redis_value(raw))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CheckpointCorruptionError("checkpoint Redis record is not valid JSON") from exc
        if not isinstance(value, dict):
            raise CheckpointCorruptionError("checkpoint Redis record must be an object")
        return cast(dict[str, object], value)

    def _require_config(
        self,
        config: RunnableConfig,
        *,
        checkpoint_id_required: bool = False,
    ) -> tuple[str, str | None]:
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            raise CheckpointScopeError("LangGraph configuration must include configurable values")

        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or thread_id != self._thread_id:
            raise CheckpointScopeError("checkpoint thread_id does not match the conversation scope")

        checkpoint_ns = configurable.get("checkpoint_ns", "")
        if not isinstance(checkpoint_ns, str):
            raise CheckpointScopeError("checkpoint_ns must be a string")

        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id is not None and not isinstance(checkpoint_id, str):
            raise CheckpointScopeError("checkpoint_id must be a string")
        if checkpoint_id_required and not checkpoint_id:
            raise CheckpointScopeError("checkpoint_id is required for this checkpoint operation")
        return checkpoint_ns, checkpoint_id

    def _check_list_scope(self, config: RunnableConfig | None) -> tuple[str | None, str | None]:
        if config is None:
            return None, None
        return self._require_config(config)

    async def _get(self, redis_key: str) -> bytes | str | None:
        try:
            return await self._redis.get(redis_key)
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc

    async def _set(
        self,
        redis_key: str,
        value: str,
        *,
        only_if_absent: bool = False,
    ) -> bool:
        try:
            result = await self._redis.set(
                redis_key,
                value,
                ex=self._ttl_seconds,
                nx=only_if_absent,
            )
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc
        return bool(result)

    async def _next_write_order(self) -> int:
        try:
            order = await self._redis.incr(self._write_order_key())
            await self._redis.expire(self._write_order_key(), self._ttl_seconds)
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc
        return int(order)

    async def _scan(self, pattern: str) -> list[str]:
        try:
            keys = [key async for key in self._redis.scan_iter(match=pattern)]
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc
        return [_decode_redis_value(key) for key in keys]

    async def _refresh_ttl(self) -> None:
        keys = await self._scan(f"{self._key_prefix}:*")
        if not keys:
            return
        try:
            for redis_key in keys:
                await self._redis.expire(redis_key, self._ttl_seconds)
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc

    def _checkpoint_record(
        self,
        record: dict[str, object],
        *,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> tuple[Checkpoint, CheckpointMetadata, str | None]:
        if record.get("schema_version") != _SCHEMA_VERSION:
            raise CheckpointCorruptionError("checkpoint Redis record has an unsupported schema")
        if record.get("checkpoint_ns") != checkpoint_ns:
            raise CheckpointCorruptionError(
                "checkpoint Redis record namespace does not match its key"
            )
        if record.get("checkpoint_id") != checkpoint_id:
            raise CheckpointCorruptionError("checkpoint Redis record ID does not match its key")

        checkpoint = self._decode_payload(record.get("checkpoint"))
        metadata = self._decode_payload(record.get("metadata"))
        parent_checkpoint_id = record.get("parent_checkpoint_id")
        if not isinstance(checkpoint, dict):
            raise CheckpointCorruptionError("checkpoint data must be an object")
        if not isinstance(metadata, dict):
            raise CheckpointCorruptionError("checkpoint metadata must be an object")
        if parent_checkpoint_id is not None and not isinstance(parent_checkpoint_id, str):
            raise CheckpointCorruptionError("checkpoint parent ID must be a string or null")
        return (
            cast(Checkpoint, checkpoint),
            cast(CheckpointMetadata, metadata),
            parent_checkpoint_id,
        )

    async def _load_channel_values(
        self,
        checkpoint_ns: str,
        checkpoint: Checkpoint,
    ) -> dict[str, Any]:
        channel_versions = checkpoint.get("channel_versions")
        if not isinstance(channel_versions, dict):
            raise CheckpointCorruptionError("checkpoint channel versions must be an object")
        channel_values: dict[str, Any] = {}
        for channel, version in channel_versions.items():
            if not isinstance(channel, str) or not isinstance(version, (str, int, float)):
                raise CheckpointCorruptionError("checkpoint channel version is invalid")
            blob_raw = await self._get(self._blob_key(checkpoint_ns, channel, version))
            if blob_raw is None:
                continue
            blob = self._load_record(blob_raw)
            if blob.get("schema_version") != _SCHEMA_VERSION:
                raise CheckpointCorruptionError("channel blob has an unsupported schema")
            if (
                blob.get("checkpoint_ns") != checkpoint_ns
                or blob.get("channel") != channel
                or blob.get("version") != version
            ):
                raise CheckpointCorruptionError("channel blob does not match its key")
            if blob.get("empty") is True:
                continue
            channel_values[channel] = self._decode_payload(blob.get("value"))
        return channel_values

    async def _load_pending_writes(
        self,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[PendingWrite]:
        writes: list[tuple[int, PendingWrite]] = []
        for redis_key in await self._scan(self._write_scan_pattern(checkpoint_ns, checkpoint_id)):
            raw = await self._get(redis_key)
            if raw is None:
                continue
            record = self._load_record(raw)
            if record.get("schema_version") != _SCHEMA_VERSION:
                raise CheckpointCorruptionError("pending write has an unsupported schema")
            if (
                record.get("checkpoint_ns") != checkpoint_ns
                or record.get("checkpoint_id") != checkpoint_id
            ):
                raise CheckpointCorruptionError("pending write does not match its key")
            order = record.get("order")
            task_id = record.get("task_id")
            channel = record.get("channel")
            if (
                not isinstance(order, int)
                or not isinstance(task_id, str)
                or not isinstance(channel, str)
            ):
                raise CheckpointCorruptionError("pending write record is malformed")
            writes.append((order, (task_id, channel, self._decode_payload(record.get("value")))))
        return [write for _, write in sorted(writes, key=lambda item: item[0])]

    async def _tuple_from_record(
        self,
        record: dict[str, object],
        *,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> CheckpointTuple:
        checkpoint, metadata, parent_checkpoint_id = self._checkpoint_record(
            record,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
        )
        channel_values = await self._load_channel_values(checkpoint_ns, checkpoint)
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": self._thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint={**checkpoint, "channel_values": channel_values},
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": self._thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
            pending_writes=await self._load_pending_writes(checkpoint_ns, checkpoint_id),
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Return one scoped checkpoint, or the newest in its namespace."""

        checkpoint_ns, checkpoint_id = self._require_config(config)
        if checkpoint_id:
            raw = await self._get(self._checkpoint_key(checkpoint_ns, checkpoint_id))
            if raw is None:
                return None
            return await self._tuple_from_record(
                self._load_record(raw),
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
            )

        candidates: list[tuple[str, dict[str, object]]] = []
        for redis_key in await self._scan(self._checkpoint_scan_pattern()):
            raw = await self._get(redis_key)
            if raw is None:
                continue
            record = self._load_record(raw)
            if record.get("checkpoint_ns") != checkpoint_ns:
                continue
            candidate_id = record.get("checkpoint_id")
            if not isinstance(candidate_id, str):
                raise CheckpointCorruptionError("checkpoint Redis record ID is invalid")
            candidates.append((candidate_id, record))
        if not candidates:
            return None
        latest_id, latest_record = max(candidates, key=lambda item: item[0])
        return await self._tuple_from_record(
            latest_record,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=latest_id,
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Yield scoped checkpoints newest first, matching LangGraph's saver contract."""

        checkpoint_ns, checkpoint_id = self._check_list_scope(config)
        before_ns: str | None = None
        before_checkpoint_id: str | None = None
        if before is not None:
            before_ns, before_checkpoint_id = self._require_config(before)
            if before_checkpoint_id is None:
                raise CheckpointScopeError("before configuration must include a checkpoint_id")
            if checkpoint_ns is not None and before_ns != checkpoint_ns:
                return

        candidates: list[tuple[str, str, dict[str, object]]] = []
        for redis_key in await self._scan(self._checkpoint_scan_pattern()):
            raw = await self._get(redis_key)
            if raw is None:
                continue
            record = self._load_record(raw)
            record_ns = record.get("checkpoint_ns")
            record_id = record.get("checkpoint_id")
            if not isinstance(record_ns, str) or not isinstance(record_id, str):
                raise CheckpointCorruptionError("checkpoint Redis record is malformed")
            if checkpoint_ns is not None and record_ns != checkpoint_ns:
                continue
            if checkpoint_id is not None and record_id != checkpoint_id:
                continue
            if (
                before_ns == record_ns
                and before_checkpoint_id is not None
                and record_id >= before_checkpoint_id
            ):
                continue
            metadata = self._decode_payload(record.get("metadata"))
            if not isinstance(metadata, dict):
                raise CheckpointCorruptionError("checkpoint metadata must be an object")
            if filter and not all(metadata.get(key) == value for key, value in filter.items()):
                continue
            candidates.append((record_id, record_ns, record))

        for index, (record_id, record_ns, record) in enumerate(sorted(candidates, reverse=True)):
            if limit is not None and index >= limit:
                break
            yield await self._tuple_from_record(
                record,
                checkpoint_ns=record_ns,
                checkpoint_id=record_id,
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Persist a checkpoint and its changed channel blobs with a 24-hour TTL."""

        checkpoint_ns, parent_checkpoint_id = self._require_config(config)
        checkpoint_id = checkpoint.get("id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise CheckpointPersistenceError("LangGraph checkpoint must include a non-empty ID")

        channel_values = checkpoint["channel_values"]
        if not isinstance(channel_values, dict):
            raise CheckpointPersistenceError("LangGraph checkpoint must include channel_values")
        checkpoint_data = {
            key: value for key, value in checkpoint.items() if key != "channel_values"
        }

        for channel, version in new_versions.items():
            if not isinstance(channel, str):
                raise CheckpointPersistenceError(
                    "LangGraph checkpoint channel names must be strings"
                )
            blob: dict[str, object] = {
                "schema_version": _SCHEMA_VERSION,
                "checkpoint_ns": checkpoint_ns,
                "channel": channel,
                "version": version,
            }
            if channel in channel_values:
                blob["empty"] = False
                blob["value"] = self._encode_payload(channel_values[channel])
            else:
                blob["empty"] = True
            await self._set(
                self._blob_key(checkpoint_ns, channel, version),
                self._dump_record(blob),
            )

        record: dict[str, object] = {
            "schema_version": _SCHEMA_VERSION,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "checkpoint": self._encode_payload(checkpoint_data),
            "metadata": self._encode_payload(get_checkpoint_metadata(config, metadata)),
            "parent_checkpoint_id": parent_checkpoint_id,
        }
        await self._set(
            self._checkpoint_key(checkpoint_ns, checkpoint_id),
            self._dump_record(record),
        )
        await self._refresh_ttl()
        return {
            "configurable": {
                "thread_id": self._thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Persist intermediate writes without overwriting normal duplicate writes."""

        checkpoint_ns, checkpoint_id = self._require_config(config, checkpoint_id_required=True)
        if checkpoint_id is None:  # Narrowing guard for type checkers.
            raise CheckpointScopeError("checkpoint_id is required for pending writes")
        if not task_id:
            raise CheckpointPersistenceError("LangGraph pending write task_id must not be empty")

        for index, (channel, value) in enumerate(writes):
            if not isinstance(channel, str):
                raise CheckpointPersistenceError("LangGraph pending write channel must be a string")
            write_index = WRITES_IDX_MAP.get(channel, index)
            redis_key = self._write_key(checkpoint_ns, checkpoint_id, task_id, write_index)
            existing = await self._get(redis_key)
            if write_index >= 0 and existing is not None:
                continue

            order = await self._next_write_order()
            record: dict[str, object] = {
                "schema_version": _SCHEMA_VERSION,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "write_index": write_index,
                "order": order,
                "task_id": task_id,
                "task_path": task_path,
                "channel": channel,
                "value": self._encode_payload(value),
            }
            inserted = await self._set(
                redis_key,
                self._dump_record(record),
                only_if_absent=write_index >= 0,
            )
            if write_index >= 0 and not inserted:
                continue
        await self._refresh_ttl()

    async def adelete_thread(self, thread_id: str) -> None:
        """Delete all checkpoint artifacts for this conversation and no other."""

        if thread_id != self._thread_id:
            raise CheckpointScopeError("checkpoint thread_id does not match the conversation scope")
        keys = await self._scan(f"{self._key_prefix}:*")
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except RedisError as exc:
            raise CheckpointPersistenceError(_REDIS_UNAVAILABLE_MESSAGE) from exc
