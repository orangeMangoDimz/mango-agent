"""Redis adapters for conversation-state ports."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis

from mango_agent.modules.conversation.domain import (
    ConversationState,
    Message,
    Participant,
    PendingConfirmation,
    PendingProposal,
)
from mango_agent.modules.conversation.domain.enums import MessageRole
from mango_agent.modules.conversation.ports import (
    ConfirmationStore,
    ConversationKey,
    ConversationStateStore,
    ProposalStore,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import (
    AttachmentId,
    EntityId,
    OperationId,
    ProjectId,
    TaskId,
    UserId,
)
from mango_agent.shared.domain.value_objects import Timestamp

DEFAULT_STATE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_PROPOSAL_TTL_SECONDS = 2 * 60 * 60
DEFAULT_CONFIRMATION_TTL_SECONDS = 2 * 60 * 60
DEFAULT_LOCK_TTL_SECONDS = 30

_STATE_SUFFIX = ":state"
_PROPOSAL_SUFFIX = ":proposal"
_CONFIRMATION_SUFFIX = ":confirmation"
_LOCK_SUFFIX = ":lock"

_STATE_SAVE_SCRIPT = """
local key = KEYS[1]
local expected = tonumber(ARGV[1])
local next_version = tonumber(ARGV[2])
local data = ARGV[3]
local ttl = tonumber(ARGV[4])
local current = redis.call("HGET", key, "version")
if current == false then
    current = 0
else
    current = tonumber(current)
end
if current ~= expected then
    return 0
end
redis.call("HSET", key, "version", next_version, "data", data)
if ttl > 0 then
    redis.call("EXPIRE", key, ttl)
end
return 1
"""

_CREATE_PENDING_SCRIPT = """
local key = KEYS[1]
local data = ARGV[1]
local ttl = tonumber(ARGV[2])
local operation_id = ARGV[3]
redis.call("HSET", key, "version", 1, "data", data, "operation_id", operation_id)
if ttl > 0 then
    redis.call("EXPIRE", key, ttl)
end
return 1
"""

_CONSUME_PENDING_SCRIPT = """
local key = KEYS[1]
local expected_op = ARGV[1]
local expected_version = tonumber(ARGV[2])
local next_version = tonumber(ARGV[3])
local new_data = ARGV[4]
local ttl = tonumber(ARGV[5])
local current_version = redis.call("HGET", key, "version")
if current_version == false then
    return 0
end
if tonumber(current_version) ~= expected_version then
    return 0
end
local current_op = redis.call("HGET", key, "operation_id")
if current_op == false then
    return 0
end
if current_op ~= expected_op then
    return 0
end
redis.call("HSET", key, "version", next_version, "data", new_data)
if ttl > 0 then
    redis.call("EXPIRE", key, ttl)
end
return 1
"""


def _decode(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return value


def _serialize_timestamp(value: Timestamp) -> str:
    return str(value)


def _serialize_id(value: EntityId) -> str:
    return str(value)


def _participant_to_dict(participant: Participant) -> dict[str, Any]:
    return {
        "user_id": _serialize_id(participant.user_id),
        "provider": participant.provider.value,
        "provider_user_id": participant.provider_user_id,
    }


def _message_to_dict(message: Message) -> dict[str, Any]:
    return {
        "role": message.role.value,
        "content": message.content,
        "timestamp": _serialize_timestamp(message.timestamp),
    }


def _pending_proposal_to_dict(proposal: PendingProposal) -> dict[str, Any]:
    return {
        "operation_id": _serialize_id(proposal.operation_id),
        "version": proposal.version,
        "content": proposal.content,
        "attachment_ids": [_serialize_id(a) for a in proposal.attachment_ids],
        "created_at": _serialize_timestamp(proposal.created_at),
        "expires_at": _serialize_timestamp(proposal.expires_at),
        "consumed": proposal.consumed,
    }


def _pending_confirmation_to_dict(confirmation: PendingConfirmation) -> dict[str, Any]:
    return {
        "operation_id": _serialize_id(confirmation.operation_id),
        "operation_type": confirmation.operation_type,
        "target_ref": confirmation.target_ref,
        "created_at": _serialize_timestamp(confirmation.created_at),
        "expires_at": _serialize_timestamp(confirmation.expires_at),
        "consumed": confirmation.consumed,
    }


def _state_to_dict(state: ConversationState) -> dict[str, Any]:
    return {
        "participant": _participant_to_dict(state.participant),
        "bot_id": state.bot_id,
        "messages": [_message_to_dict(m) for m in state.messages],
        "last_project_id": (
            _serialize_id(state.last_project_id) if state.last_project_id else None
        ),
        "last_task_id": (_serialize_id(state.last_task_id) if state.last_task_id else None),
        "temp_attachment_ids": [_serialize_id(a) for a in state.temp_attachment_ids],
        "checkpoint_ref": state.checkpoint_ref,
        "pending_proposal": (
            _pending_proposal_to_dict(state.pending_proposal) if state.pending_proposal else None
        ),
        "pending_confirmation": (
            _pending_confirmation_to_dict(state.pending_confirmation)
            if state.pending_confirmation
            else None
        ),
        "created_at": _serialize_timestamp(state.created_at),
        "updated_at": _serialize_timestamp(state.updated_at),
    }


def _to_json(obj: ConversationState | PendingProposal | PendingConfirmation) -> str:
    if isinstance(obj, ConversationState):
        return json.dumps(_state_to_dict(obj), sort_keys=True)
    if isinstance(obj, PendingProposal):
        return json.dumps(_pending_proposal_to_dict(obj), sort_keys=True)
    if isinstance(obj, PendingConfirmation):
        return json.dumps(_pending_confirmation_to_dict(obj), sort_keys=True)
    raise TypeError(f"Unsupported object type: {type(obj).__name__}")


def _parse_timestamp(value: str) -> Timestamp:
    return Timestamp.from_datetime(datetime.fromisoformat(value))


def _parse_optional_id[T: EntityId](value: Any, cls: type[T]) -> T | None:
    if value is None:
        return None
    return cls.from_string(value)


def _parse_id_list[T: EntityId](value: Any, cls: type[T]) -> tuple[T, ...]:
    if not value:
        return ()
    return tuple(cls.from_string(v) for v in value)


def _participant_from_dict(data: dict[str, Any]) -> Participant:
    return Participant(
        user_id=UserId.from_string(data["user_id"]),
        provider=Provider(data["provider"]),
        provider_user_id=data["provider_user_id"],
    )


def _message_from_dict(data: dict[str, Any]) -> Message:
    return Message(
        role=MessageRole(data["role"]),
        content=data["content"],
        timestamp=_parse_timestamp(data["timestamp"]),
    )


def _pending_proposal_from_dict(data: dict[str, Any]) -> PendingProposal:
    return PendingProposal(
        operation_id=OperationId.from_string(data["operation_id"]),
        version=data["version"],
        content=data["content"],
        attachment_ids=_parse_id_list(data["attachment_ids"], AttachmentId),
        created_at=_parse_timestamp(data["created_at"]),
        expires_at=_parse_timestamp(data["expires_at"]),
        consumed=data["consumed"],
    )


def _pending_confirmation_from_dict(data: dict[str, Any]) -> PendingConfirmation:
    return PendingConfirmation(
        operation_id=OperationId.from_string(data["operation_id"]),
        operation_type=data["operation_type"],
        target_ref=data["target_ref"],
        created_at=_parse_timestamp(data["created_at"]),
        expires_at=_parse_timestamp(data["expires_at"]),
        consumed=data["consumed"],
    )


def _state_from_dict(data: dict[str, Any]) -> ConversationState:
    return ConversationState(
        participant=_participant_from_dict(data["participant"]),
        bot_id=data["bot_id"],
        messages=tuple(_message_from_dict(m) for m in data["messages"]),
        last_project_id=_parse_optional_id(data["last_project_id"], ProjectId),
        last_task_id=_parse_optional_id(data["last_task_id"], TaskId),
        temp_attachment_ids=_parse_id_list(data["temp_attachment_ids"], AttachmentId),
        checkpoint_ref=data["checkpoint_ref"],
        pending_proposal=(
            _pending_proposal_from_dict(data["pending_proposal"])
            if data["pending_proposal"]
            else None
        ),
        pending_confirmation=(
            _pending_confirmation_from_dict(data["pending_confirmation"])
            if data["pending_confirmation"]
            else None
        ),
        created_at=_parse_timestamp(data["created_at"]),
        updated_at=_parse_timestamp(data["updated_at"]),
    )


class RedisConversationStateStore(ConversationStateStore):
    """Redis-backed optimistic-locking store for conversation state."""

    def __init__(self, redis: Redis, ttl_seconds: int = DEFAULT_STATE_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _redis_key(self, key: ConversationKey) -> str:
        return f"{key}{_STATE_SUFFIX}"

    async def load(self, key: ConversationKey) -> tuple[ConversationState, int] | None:
        redis_key = self._redis_key(key)
        version_raw = await self._redis.hget(redis_key, "version")
        data_raw = await self._redis.hget(redis_key, "data")
        if version_raw is None or data_raw is None:
            return None
        version = int(_decode(version_raw))
        data = json.loads(_decode(data_raw))
        return _state_from_dict(data), version

    async def save(
        self, key: ConversationKey, state: ConversationState, expected_version: int
    ) -> bool:
        redis_key = self._redis_key(key)
        result = await self._redis.eval(
            _STATE_SAVE_SCRIPT,
            1,
            redis_key,
            expected_version,
            expected_version + 1,
            _to_json(state),
            self._ttl_seconds,
        )
        return bool(result)

    async def clear(self, key: ConversationKey) -> None:
        await self._redis.delete(self._redis_key(key))


class RedisProposalStore(ProposalStore):
    """Redis-backed optimistic-locking store for pending proposals."""

    def __init__(self, redis: Redis, ttl_seconds: int = DEFAULT_PROPOSAL_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _redis_key(self, key: ConversationKey) -> str:
        return f"{key}{_PROPOSAL_SUFFIX}"

    async def create(self, key: ConversationKey, proposal: PendingProposal) -> int:
        redis_key = self._redis_key(key)
        await self._redis.eval(
            _CREATE_PENDING_SCRIPT,
            1,
            redis_key,
            _to_json(proposal),
            self._ttl_seconds,
            str(proposal.operation_id),
        )
        return 1

    async def get(self, key: ConversationKey) -> tuple[PendingProposal, int] | None:
        redis_key = self._redis_key(key)
        version_raw = await self._redis.hget(redis_key, "version")
        data_raw = await self._redis.hget(redis_key, "data")
        if version_raw is None or data_raw is None:
            return None
        version = int(_decode(version_raw))
        data = json.loads(_decode(data_raw))
        return _pending_proposal_from_dict(data), version

    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        redis_key = self._redis_key(key)
        current = await self.get(key)
        if current is None:
            return False
        proposal, _ = current
        if proposal.consumed:
            return False
        if proposal.operation_id != operation_id:
            return False
        consumed = proposal.consume()
        result = await self._redis.eval(
            _CONSUME_PENDING_SCRIPT,
            1,
            redis_key,
            str(operation_id),
            expected_version,
            expected_version + 1,
            _to_json(consumed),
            self._ttl_seconds,
        )
        return bool(result)

    async def clear(self, key: ConversationKey) -> None:
        await self._redis.delete(self._redis_key(key))


class RedisConfirmationStore(ConfirmationStore):
    """Redis-backed optimistic-locking store for pending confirmations."""

    def __init__(self, redis: Redis, ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _redis_key(self, key: ConversationKey) -> str:
        return f"{key}{_CONFIRMATION_SUFFIX}"

    async def create(self, key: ConversationKey, confirmation: PendingConfirmation) -> int:
        redis_key = self._redis_key(key)
        await self._redis.eval(
            _CREATE_PENDING_SCRIPT,
            1,
            redis_key,
            _to_json(confirmation),
            self._ttl_seconds,
            str(confirmation.operation_id),
        )
        return 1

    async def get(self, key: ConversationKey) -> tuple[PendingConfirmation, int] | None:
        redis_key = self._redis_key(key)
        version_raw = await self._redis.hget(redis_key, "version")
        data_raw = await self._redis.hget(redis_key, "data")
        if version_raw is None or data_raw is None:
            return None
        version = int(_decode(version_raw))
        data = json.loads(_decode(data_raw))
        return _pending_confirmation_from_dict(data), version

    async def consume(
        self, key: ConversationKey, operation_id: OperationId, expected_version: int
    ) -> bool:
        redis_key = self._redis_key(key)
        current = await self.get(key)
        if current is None:
            return False
        confirmation, _ = current
        if confirmation.consumed:
            return False
        if confirmation.operation_id != operation_id:
            return False
        consumed = confirmation.consume()
        result = await self._redis.eval(
            _CONSUME_PENDING_SCRIPT,
            1,
            redis_key,
            str(operation_id),
            expected_version,
            expected_version + 1,
            _to_json(consumed),
            self._ttl_seconds,
        )
        return bool(result)

    async def clear(self, key: ConversationKey) -> None:
        await self._redis.delete(self._redis_key(key))


class RedisProcessingLock:
    """Short-lived Redis-backed lock for state transitions."""

    def __init__(
        self,
        redis: Redis,
        key: str,
        value: str | None = None,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._key = f"{key}{_LOCK_SUFFIX}"
        self._value = value or str(uuid.uuid4())
        self._ttl_seconds = ttl_seconds
        self._acquired = False

    async def acquire(self) -> bool:
        if self._acquired:
            return True
        result = await self._redis.set(self._key, self._value, nx=True, ex=self._ttl_seconds)
        self._acquired = result is not None
        return self._acquired

    async def release(self) -> bool:
        if not self._acquired:
            return False
        script = (
            "if redis.call('GET', KEYS[1]) == ARGV[1] then "
            "return redis.call('DEL', KEYS[1]) else return 0 end"
        )
        result = await self._redis.eval(script, 1, self._key, self._value)
        self._acquired = False
        return bool(result)

    async def __aenter__(self) -> RedisProcessingLock:
        if not await self.acquire():
            raise RuntimeError(f"Could not acquire lock for {self._key}")
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.release()
