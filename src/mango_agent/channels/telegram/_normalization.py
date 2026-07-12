"""Map Telegram SDK objects to provider-independent channel contracts."""

from __future__ import annotations

from typing import final

import telegram
from telegram import Message, PhotoSize, User

from mango_agent.modules.attachments.application.use_cases import RegisterPendingUpload
from mango_agent.modules.attachments.ports.storage import UploadRequest
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    AttachmentDescriptor,
    NormalizedInboundMessage,
    ReplyReference,
)
from mango_agent.shared.domain.errors import MangoError
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope

_DEFAULT_PHOTO_FILENAME = "photo.jpg"
_DEFAULT_PHOTO_MIME_TYPE = "image/jpeg"


@final
class TelegramAttachmentError(MangoError):
    """Raised when a Telegram attachment cannot be normalized or uploaded."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="internal_error")


def _display_name(user: User) -> str:
    return (user.full_name or user.first_name or "Telegram User").strip()


def _reply_reference(message: Message) -> ReplyReference | None:
    if message.reply_to_message is None:
        return None
    return ReplyReference(
        message_id=str(message.reply_to_message.message_id),
        conversation_id=str(message.chat.id),
        thread_id=(str(message.message_thread_id) if message.message_thread_id else None),
    )


async def upload_photo_attachment(
    bot: telegram.Bot,
    register_upload: RegisterPendingUpload,
    actor: ActorScope,
    photo: PhotoSize,
    original_filename: str = _DEFAULT_PHOTO_FILENAME,
) -> AttachmentDescriptor:
    """Download a Telegram photo and register it as an internal attachment."""

    file = await bot.get_file(photo.file_id)
    content = bytes(await file.download_as_bytearray())
    request = UploadRequest(
        content=content,
        original_filename=original_filename,
        mime_type=_DEFAULT_PHOTO_MIME_TYPE,
        uploader_user_id=actor.user_id,
    )
    result = await register_upload(actor, request)
    if result.is_failure:
        raise TelegramAttachmentError(result.error.message)

    attachment = result.value
    return AttachmentDescriptor(
        attachment_id=attachment.id,
        media_type="image",
        original_filename=original_filename,
        mime_type=_DEFAULT_PHOTO_MIME_TYPE,
    )


async def upload_message_attachments(
    bot: telegram.Bot,
    register_upload: RegisterPendingUpload,
    actor: ActorScope,
    message: Message,
) -> tuple[AttachmentDescriptor, ...]:
    """Download all supported Telegram attachments and register them."""

    if not message.photo:
        return ()

    largest_photo = max(message.photo, key=lambda photo: photo.file_size or 0)
    descriptor = await upload_photo_attachment(bot, register_upload, actor, largest_photo)
    return (descriptor,)


def build_normalized_message(
    bot_id: str,
    agent_command: str,
    update: telegram.Update,
    attachments: tuple[AttachmentDescriptor, ...] = (),
) -> NormalizedInboundMessage:
    """Convert a Telegram message update into a normalized inbound message."""

    message = update.effective_message
    if not isinstance(message, Message):
        raise TelegramAttachmentError("update has no accessible message")

    user = message.from_user
    if user is None:
        raise TelegramAttachmentError("message has no sender")

    return NormalizedInboundMessage(
        provider=Provider.TELEGRAM,
        bot_id=bot_id,
        agent_command=agent_command,
        provider_event_id=str(update.update_id),
        conversation_id=str(message.chat.id),
        thread_id=(str(message.message_thread_id) if message.message_thread_id else None),
        provider_user_id=str(user.id),
        display_name=_display_name(user),
        username=user.username,
        message_id=str(message.message_id),
        text=message.text or message.caption,
        attachments=attachments,
        reply_to=_reply_reference(message),
        received_at=Timestamp.now(),
    )


def build_normalized_callback(
    bot_id: str,
    agent_command: str,
    update: telegram.Update,
    kind: str,
    operation_id: str,
) -> NormalizedInboundMessage:
    """Convert a Telegram callback query into a normalized inbound message."""

    query = update.callback_query
    if query is None or query.message is None:
        raise TelegramAttachmentError("update has no callback query")

    message = query.message
    if not isinstance(message, Message):
        raise TelegramAttachmentError("callback query has no accessible message")

    user = query.from_user
    if user is None:
        raise TelegramAttachmentError("callback query has no sender")

    return NormalizedInboundMessage(
        provider=Provider.TELEGRAM,
        bot_id=bot_id,
        agent_command=agent_command,
        provider_event_id=str(update.update_id),
        conversation_id=str(message.chat.id),
        thread_id=(str(message.message_thread_id) if message.message_thread_id else None),
        provider_user_id=str(user.id),
        display_name=_display_name(user),
        username=user.username,
        message_id=str(message.message_id),
        text=f"{kind}:{operation_id}",
        attachments=(),
        reply_to=ReplyReference(message_id=str(message.message_id)),
        received_at=Timestamp.now(),
    )
