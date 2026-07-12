"""Tests for provider-independent channel message contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    ApprovalAction,
    ApprovalActionKind,
    AttachmentDescriptor,
    DeliveryMetadata,
    NormalizedInboundMessage,
    NormalizedOutboundResponse,
    ReplyReference,
    ResponseKind,
)
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, OperationId, TaskId
from mango_agent.shared.domain.value_objects import Timestamp


def _inbound_message() -> NormalizedInboundMessage:
    return NormalizedInboundMessage(
        provider=Provider.TELEGRAM,
        bot_id="task-bot",
        agent_command="task_management",
        provider_event_id="update-123",
        conversation_id="conversation-123",
        thread_id="thread-123",
        provider_user_id="provider-user-123",
        display_name="Mango User",
        username="mango-user",
        message_id="message-123",
        text="Create a task from this image",
        attachments=(
            AttachmentDescriptor(
                attachment_id=AttachmentId.generate(),
                media_type="image",
                original_filename="screenshot.png",
                mime_type="image/png",
            ),
        ),
        reply_to=ReplyReference(message_id="message-122"),
        received_at=Timestamp.from_datetime(datetime(2026, 7, 12, tzinfo=UTC)),
    )


def test_inbound_message_round_trips_through_json_safe_contract() -> None:
    message = _inbound_message()

    payload = message.to_dict()
    json_payload = json.loads(json.dumps(payload))

    assert NormalizedInboundMessage.from_dict(json_payload) == message
    assert message.message_text == message.text
    assert payload["attachments"][0]["storage_id"] == str(message.attachments[0].attachment_id)


def test_attachment_descriptor_rejects_storage_and_transport_secrets() -> None:
    attachment_id = AttachmentId.generate()

    with pytest.raises(ValidationError, match="must not contain"):
        AttachmentDescriptor.from_dict(
            {
                "storage_id": str(attachment_id),
                "media_type": "image",
                "object_key": "private/user/object.png",
            }
        )

    descriptor = AttachmentDescriptor(attachment_id=attachment_id, media_type="image")
    assert not hasattr(descriptor, "object_key")
    assert not hasattr(descriptor, "url")
    assert not hasattr(descriptor, "bytes")


def test_inbound_message_rejects_naive_received_timestamp() -> None:
    payload = _inbound_message().to_dict()
    payload["received_at"] = "2026-07-12T00:00:00"

    with pytest.raises(ValidationError, match="timezone-aware"):
        NormalizedInboundMessage.from_dict(payload)


def test_confirmation_response_round_trips_through_json_safe_contract() -> None:
    operation_id = OperationId.generate()
    response = NormalizedOutboundResponse(
        kind=ResponseKind.CONFIRMATION,
        text="Delete this task?",
        reply_to=ReplyReference(message_id="message-123", thread_id="thread-123"),
        operation_id=operation_id,
        approval_actions=(
            ApprovalAction(ApprovalActionKind.CONFIRM, "Delete", operation_id),
            ApprovalAction(ApprovalActionKind.CANCEL, "Keep", operation_id),
        ),
        delivery_metadata=(DeliveryMetadata("correlation_id", "corr-123"),),
    )

    payload = json.loads(json.dumps(response.to_dict()))

    assert NormalizedOutboundResponse.from_dict(payload) == response


def test_response_kind_rejects_actions_outside_approval_flow() -> None:
    operation_id = OperationId.generate()

    with pytest.raises(ValidationError, match="only valid for proposal or confirmation"):
        NormalizedOutboundResponse(
            kind=ResponseKind.FINAL_TEXT,
            text="Done",
            approval_actions=(ApprovalAction(ApprovalActionKind.APPROVE, "Approve", operation_id),),
        )


def test_each_response_kind_has_a_valid_provider_independent_shape() -> None:
    operation_id = OperationId.generate()
    task_id = TaskId.generate()
    attachment = AttachmentDescriptor(AttachmentId.generate(), "image")
    approve = ApprovalAction(ApprovalActionKind.APPROVE, "Approve", operation_id)
    confirm = ApprovalAction(ApprovalActionKind.CONFIRM, "Confirm", operation_id)

    responses = (
        NormalizedOutboundResponse.final_text("Done"),
        NormalizedOutboundResponse.follow_up("Which project should I use?"),
        NormalizedOutboundResponse(
            kind=ResponseKind.PROPOSAL,
            text="Create the proposed task?",
            operation_id=operation_id,
            approval_actions=(approve,),
        ),
        NormalizedOutboundResponse(
            kind=ResponseKind.CONFIRMATION,
            text="Delete the task?",
            operation_id=operation_id,
            approval_actions=(confirm,),
        ),
        NormalizedOutboundResponse(
            kind=ResponseKind.TASK_LIST,
            text="Here are your tasks.",
            task_ids=(task_id,),
        ),
        NormalizedOutboundResponse(
            kind=ResponseKind.TASK_DETAILS,
            text="Task details.",
            task_ids=(task_id,),
        ),
        NormalizedOutboundResponse(
            kind=ResponseKind.ATTACHMENT,
            attachments=(attachment,),
        ),
        NormalizedOutboundResponse.error("not_found", "Task not found."),
    )

    assert {response.kind for response in responses} == set(ResponseKind)
