"""Provider-independent message contracts shared by channel adapters and agents.

The contracts deliberately contain only stable identifiers and user-visible
metadata.  They never carry provider SDK objects, attachment bytes, object
keys, or temporary URLs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Self, final

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, OperationId, TaskId
from mango_agent.shared.domain.value_objects import Timestamp

__all__ = [
    "ApprovalAction",
    "ApprovalActionKind",
    "AttachmentDescriptor",
    "DeliveryMetadata",
    "NormalizedInboundMessage",
    "NormalizedOutboundResponse",
    "ReplyReference",
    "ResponseKind",
]

_FORBIDDEN_ATTACHMENT_FIELDS = frozenset(
    {
        "bytes",
        "content",
        "data",
        "object_key",
        "presigned_url",
        "url",
    }
)


def _require_nonempty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must not be empty")
    return value.strip()


def _optional_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_nonempty_string(value, field_name)


def _require_mapping(data: Mapping[str, Any], type_name: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValidationError(f"{type_name} payload must be a mapping")
    return data


def _require_value(data: Mapping[str, Any], field_name: str, type_name: str) -> Any:
    try:
        return data[field_name]
    except KeyError as exc:
        raise ValidationError(f"{type_name} payload is missing {field_name}") from exc


@final
@dataclass(frozen=True, slots=True)
class AttachmentDescriptor:
    """Safe metadata for an uploaded attachment.

    ``attachment_id`` is the sole stable storage reference exposed to agents.
    The channel layer owns any provider download, object key, and URL handling.
    """

    attachment_id: AttachmentId
    media_type: str
    original_filename: str | None = None
    mime_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attachment_id, AttachmentId):
            raise ValidationError("attachment_id must be an AttachmentId")
        object.__setattr__(
            self,
            "media_type",
            _require_nonempty_string(self.media_type, "media_type"),
        )
        object.__setattr__(
            self,
            "original_filename",
            _optional_string(self.original_filename, "original_filename"),
        )
        object.__setattr__(self, "mime_type", _optional_string(self.mime_type, "mime_type"))

    @property
    def storage_id(self) -> AttachmentId:
        """Compatibility name matching the normalized wire contract."""
        return self.attachment_id

    def to_dict(self) -> dict[str, str | None]:
        return {
            "storage_id": str(self.attachment_id),
            "media_type": self.media_type,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "attachment descriptor")
        forbidden = sorted(_FORBIDDEN_ATTACHMENT_FIELDS.intersection(payload))
        if forbidden:
            fields = ", ".join(forbidden)
            raise ValidationError(f"attachment descriptor must not contain: {fields}")
        storage_id = payload.get("storage_id", payload.get("attachment_id"))
        if not isinstance(storage_id, str):
            raise ValidationError("attachment descriptor storage_id must be a string")
        return cls(
            attachment_id=AttachmentId.from_string(storage_id),
            media_type=_require_value(payload, "media_type", "attachment descriptor"),
            original_filename=payload.get("original_filename"),
            mime_type=payload.get("mime_type"),
        )


@final
@dataclass(frozen=True, slots=True)
class ReplyReference:
    """Reference to a provider message in the current conversation."""

    message_id: str
    conversation_id: str | None = None
    thread_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "message_id",
            _require_nonempty_string(self.message_id, "message_id"),
        )
        object.__setattr__(
            self,
            "conversation_id",
            _optional_string(self.conversation_id, "conversation_id"),
        )
        object.__setattr__(self, "thread_id", _optional_string(self.thread_id, "thread_id"))

    def to_dict(self) -> dict[str, str | None]:
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "reply reference")
        return cls(
            message_id=_require_value(payload, "message_id", "reply reference"),
            conversation_id=payload.get("conversation_id"),
            thread_id=payload.get("thread_id"),
        )


@final
@dataclass(frozen=True, slots=True)
class NormalizedInboundMessage:
    """Provider-independent input delivered to a selected agent.

    ``agent_command`` is supplied by the channel configuration. It must not be
    inferred from natural-language content.
    """

    provider: Provider
    bot_id: str
    agent_command: str
    provider_event_id: str
    conversation_id: str
    thread_id: str | None
    provider_user_id: str
    display_name: str | None
    username: str | None
    message_id: str
    text: str | None
    attachments: tuple[AttachmentDescriptor, ...]
    reply_to: ReplyReference | None
    received_at: Timestamp

    def __post_init__(self) -> None:
        if not isinstance(self.provider, Provider):
            raise ValidationError("provider must be a Provider value")
        if not isinstance(self.received_at, Timestamp):
            raise ValidationError("received_at must be a Timestamp")

        for field_name in (
            "bot_id",
            "agent_command",
            "provider_event_id",
            "conversation_id",
            "provider_user_id",
            "message_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_nonempty_string(getattr(self, field_name), field_name),
            )

        object.__setattr__(self, "thread_id", _optional_string(self.thread_id, "thread_id"))
        object.__setattr__(
            self,
            "display_name",
            _optional_string(self.display_name, "display_name"),
        )
        object.__setattr__(self, "username", _optional_string(self.username, "username"))

        if self.text is not None and not isinstance(self.text, str):
            raise ValidationError("text must be a string or None")
        if self.text is not None and not self.text.strip():
            raise ValidationError("text must not be blank when provided")

        attachments = tuple(self.attachments)
        if not all(isinstance(attachment, AttachmentDescriptor) for attachment in attachments):
            raise ValidationError("attachments must contain AttachmentDescriptor values")
        if self.text is None and not attachments:
            raise ValidationError("inbound message must contain text or an attachment")
        if self.reply_to is not None and not isinstance(self.reply_to, ReplyReference):
            raise ValidationError("reply_to must be a ReplyReference or None")
        object.__setattr__(self, "attachments", attachments)

    @property
    def message_text(self) -> str | None:
        """Compatibility alias for the previous agent-local request field."""
        return self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "bot_id": self.bot_id,
            "agent_command": self.agent_command,
            "provider_event_id": self.provider_event_id,
            "conversation_id": self.conversation_id,
            "thread_id": self.thread_id,
            "provider_user_id": self.provider_user_id,
            "display_name": self.display_name,
            "username": self.username,
            "message_id": self.message_id,
            "text": self.text,
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "reply_to": self.reply_to.to_dict() if self.reply_to else None,
            "received_at": str(self.received_at),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "normalized inbound message")
        attachments_raw = payload.get("attachments", ())
        if not isinstance(attachments_raw, (list, tuple)):
            raise ValidationError("attachments must be a list or tuple")
        reply_to_raw = payload.get("reply_to")
        if reply_to_raw is not None and not isinstance(reply_to_raw, Mapping):
            raise ValidationError("reply_to must be a mapping or None")
        received_at_raw = _require_value(payload, "received_at", "normalized inbound message")
        if not isinstance(received_at_raw, str):
            raise ValidationError("received_at must be an ISO-8601 string")
        provider_raw = _require_value(payload, "provider", "normalized inbound message")
        if not isinstance(provider_raw, str):
            raise ValidationError("provider must be a string")
        try:
            provider = Provider(provider_raw)
        except ValueError as exc:
            raise ValidationError(f"unsupported provider: {provider_raw}") from exc
        try:
            received_at = Timestamp.from_datetime(datetime.fromisoformat(received_at_raw))
        except ValueError as exc:
            raise ValidationError("received_at must be an ISO-8601 timestamp") from exc
        return cls(
            provider=provider,
            bot_id=_require_value(payload, "bot_id", "normalized inbound message"),
            agent_command=_require_value(payload, "agent_command", "normalized inbound message"),
            provider_event_id=_require_value(
                payload, "provider_event_id", "normalized inbound message"
            ),
            conversation_id=_require_value(
                payload,
                "conversation_id",
                "normalized inbound message",
            ),
            thread_id=payload.get("thread_id"),
            provider_user_id=_require_value(
                payload, "provider_user_id", "normalized inbound message"
            ),
            display_name=payload.get("display_name"),
            username=payload.get("username"),
            message_id=_require_value(payload, "message_id", "normalized inbound message"),
            text=payload.get("text"),
            attachments=tuple(AttachmentDescriptor.from_dict(item) for item in attachments_raw),
            reply_to=ReplyReference.from_dict(reply_to_raw) if reply_to_raw else None,
            received_at=received_at,
        )


class ResponseKind(StrEnum):
    """Provider-independent response categories understood by channel adapters."""

    FINAL_TEXT = "final_text"
    FOLLOW_UP = "follow_up"
    PROPOSAL = "proposal"
    CONFIRMATION = "confirmation"
    TASK_LIST = "task_list"
    TASK_DETAILS = "task_details"
    ATTACHMENT = "attachment"
    ERROR = "error"


class ApprovalActionKind(StrEnum):
    """Logical approval controls that a provider may render when supported."""

    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"
    CONFIRM = "confirm"
    CANCEL = "cancel"


@final
@dataclass(frozen=True, slots=True)
class ApprovalAction:
    """A provider-neutral action bound to a workflow operation."""

    kind: ApprovalActionKind
    label: str
    operation_id: OperationId

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ApprovalActionKind):
            raise ValidationError("approval action kind must be an ApprovalActionKind")
        if not isinstance(self.operation_id, OperationId):
            raise ValidationError("approval action operation_id must be an OperationId")
        object.__setattr__(self, "label", _require_nonempty_string(self.label, "label"))

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "label": self.label,
            "operation_id": str(self.operation_id),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "approval action")
        kind = _require_value(payload, "kind", "approval action")
        operation_id = _require_value(payload, "operation_id", "approval action")
        if not isinstance(kind, str):
            raise ValidationError("approval action kind must be a string")
        if not isinstance(operation_id, str):
            raise ValidationError("approval action operation_id must be a string")
        try:
            action_kind = ApprovalActionKind(kind)
        except ValueError as exc:
            raise ValidationError(f"unsupported approval action kind: {kind}") from exc
        return cls(
            kind=action_kind,
            label=_require_value(payload, "label", "approval action"),
            operation_id=OperationId.from_string(operation_id),
        )


@final
@dataclass(frozen=True, slots=True)
class DeliveryMetadata:
    """Provider-neutral delivery hint or result metadata."""

    key: str
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _require_nonempty_string(self.key, "delivery key"))
        object.__setattr__(self, "value", _require_nonempty_string(self.value, "delivery value"))

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "delivery metadata")
        return cls(
            key=_require_value(payload, "key", "delivery metadata"),
            value=_require_value(payload, "value", "delivery metadata"),
        )


@final
@dataclass(frozen=True, slots=True)
class NormalizedOutboundResponse:
    """Provider-independent agent result for channel formatting and delivery."""

    kind: ResponseKind
    text: str | None = None
    reply_to: ReplyReference | None = None
    approval_actions: tuple[ApprovalAction, ...] = ()
    attachments: tuple[AttachmentDescriptor, ...] = ()
    task_ids: tuple[TaskId, ...] = ()
    operation_id: OperationId | None = None
    error_code: str | None = None
    delivery_metadata: tuple[DeliveryMetadata, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResponseKind):
            raise ValidationError("response kind must be a ResponseKind")
        if self.text is not None and (not isinstance(self.text, str) or not self.text.strip()):
            raise ValidationError("response text must not be blank when provided")
        if self.reply_to is not None and not isinstance(self.reply_to, ReplyReference):
            raise ValidationError("reply_to must be a ReplyReference or None")
        if self.operation_id is not None and not isinstance(self.operation_id, OperationId):
            raise ValidationError("operation_id must be an OperationId or None")

        approval_actions = tuple(self.approval_actions)
        attachments = tuple(self.attachments)
        task_ids = tuple(self.task_ids)
        delivery_metadata = tuple(self.delivery_metadata)
        if not all(isinstance(action, ApprovalAction) for action in approval_actions):
            raise ValidationError("approval_actions must contain ApprovalAction values")
        if not all(isinstance(attachment, AttachmentDescriptor) for attachment in attachments):
            raise ValidationError("attachments must contain AttachmentDescriptor values")
        if not all(isinstance(task_id, TaskId) for task_id in task_ids):
            raise ValidationError("task_ids must contain TaskId values")
        if not all(isinstance(metadata, DeliveryMetadata) for metadata in delivery_metadata):
            raise ValidationError("delivery_metadata must contain DeliveryMetadata values")
        object.__setattr__(self, "approval_actions", approval_actions)
        object.__setattr__(self, "attachments", attachments)
        object.__setattr__(self, "task_ids", task_ids)
        object.__setattr__(self, "delivery_metadata", delivery_metadata)
        object.__setattr__(self, "error_code", _optional_string(self.error_code, "error_code"))
        self._validate_kind_requirements()

    @classmethod
    def final_text(cls, text: str, *, reply_to: ReplyReference | None = None) -> Self:
        return cls(kind=ResponseKind.FINAL_TEXT, text=text, reply_to=reply_to)

    @classmethod
    def follow_up(cls, text: str, *, reply_to: ReplyReference | None = None) -> Self:
        return cls(kind=ResponseKind.FOLLOW_UP, text=text, reply_to=reply_to)

    @classmethod
    def error(cls, code: str, text: str, *, reply_to: ReplyReference | None = None) -> Self:
        return cls(kind=ResponseKind.ERROR, error_code=code, text=text, reply_to=reply_to)

    def _validate_kind_requirements(self) -> None:
        text_required = frozenset(
            {
                ResponseKind.FINAL_TEXT,
                ResponseKind.FOLLOW_UP,
                ResponseKind.PROPOSAL,
                ResponseKind.CONFIRMATION,
                ResponseKind.TASK_LIST,
                ResponseKind.TASK_DETAILS,
                ResponseKind.ERROR,
            }
        )
        if self.kind in text_required and self.text is None:
            raise ValidationError(f"{self.kind.value} response requires text")
        if self.kind in {ResponseKind.PROPOSAL, ResponseKind.CONFIRMATION}:
            if self.operation_id is None:
                raise ValidationError(f"{self.kind.value} response requires operation_id")
            if not self.approval_actions:
                raise ValidationError(f"{self.kind.value} response requires approval_actions")
            if any(action.operation_id != self.operation_id for action in self.approval_actions):
                raise ValidationError(
                    "approval action operation_id must match response operation_id"
                )
        elif self.approval_actions:
            raise ValidationError(
                "approval_actions are only valid for proposal or confirmation responses"
            )
        if self.kind == ResponseKind.TASK_DETAILS and len(self.task_ids) != 1:
            raise ValidationError("task_details response requires exactly one task_id")
        if self.kind == ResponseKind.ATTACHMENT and not self.attachments:
            raise ValidationError("attachment response requires attachments")
        if self.kind == ResponseKind.ERROR and self.error_code is None:
            raise ValidationError("error response requires error_code")
        if self.kind != ResponseKind.ERROR and self.error_code is not None:
            raise ValidationError("error_code is only valid for error responses")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "reply_to": self.reply_to.to_dict() if self.reply_to else None,
            "approval_actions": [action.to_dict() for action in self.approval_actions],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "task_ids": [str(task_id) for task_id in self.task_ids],
            "operation_id": str(self.operation_id) if self.operation_id else None,
            "error_code": self.error_code,
            "delivery_metadata": [metadata.to_dict() for metadata in self.delivery_metadata],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        payload = _require_mapping(data, "normalized outbound response")
        kind = _require_value(payload, "kind", "normalized outbound response")
        if not isinstance(kind, str):
            raise ValidationError("response kind must be a string")
        try:
            response_kind = ResponseKind(kind)
        except ValueError as exc:
            raise ValidationError(f"unsupported response kind: {kind}") from exc
        reply_to_raw = payload.get("reply_to")
        operation_id_raw = payload.get("operation_id")
        collections = {
            "approval_actions": payload.get("approval_actions", ()),
            "attachments": payload.get("attachments", ()),
            "task_ids": payload.get("task_ids", ()),
            "delivery_metadata": payload.get("delivery_metadata", ()),
        }
        if any(not isinstance(value, (list, tuple)) for value in collections.values()):
            raise ValidationError("response collection fields must be lists or tuples")
        if reply_to_raw is not None and not isinstance(reply_to_raw, Mapping):
            raise ValidationError("reply_to must be a mapping or None")
        if operation_id_raw is not None and not isinstance(operation_id_raw, str):
            raise ValidationError("operation_id must be a string or None")
        return cls(
            kind=response_kind,
            text=payload.get("text"),
            reply_to=ReplyReference.from_dict(reply_to_raw) if reply_to_raw else None,
            approval_actions=tuple(
                ApprovalAction.from_dict(item) for item in collections["approval_actions"]
            ),
            attachments=tuple(
                AttachmentDescriptor.from_dict(item) for item in collections["attachments"]
            ),
            task_ids=tuple(TaskId.from_string(item) for item in collections["task_ids"]),
            operation_id=OperationId.from_string(operation_id_raw) if operation_id_raw else None,
            error_code=payload.get("error_code"),
            delivery_metadata=tuple(
                DeliveryMetadata.from_dict(item) for item in collections["delivery_metadata"]
            ),
        )
