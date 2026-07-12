"""Deliver provider-independent responses to Telegram."""

from __future__ import annotations

import time

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from mango_agent.modules.attachments.application.use_cases import GenerateAccess
from mango_agent.shared.channel_contracts import (
    ApprovalAction,
    AttachmentDescriptor,
    NormalizedOutboundResponse,
    ResponseKind,
)
from mango_agent.shared.domain.errors import MangoError
from mango_agent.shared.infrastructure.logging import logger
from mango_agent.shared.infrastructure.metrics import METRICS
from mango_agent.shared.ports.actor_scope import ActorScope


class TelegramDeliveryError(MangoError):
    """Raised when a normalized response cannot be delivered to Telegram."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="internal_error")


def _approval_markup(actions: tuple[ApprovalAction, ...]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                action.label,
                callback_data=f"{action.kind.value}:{action.operation_id}",
            )
        ]
        for action in actions
    ]
    return InlineKeyboardMarkup(buttons)


async def _send_attachment(
    bot: telegram.Bot,
    chat_id: int,
    attachment: AttachmentDescriptor,
    caption: str | None,
    reply_to: int | None,
    generate_access: GenerateAccess,
    actor: ActorScope,
) -> None:
    url_result = await generate_access(actor, attachment.attachment_id)
    if url_result.is_failure:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Could not retrieve attachment {attachment.attachment_id}.",
            reply_to_message_id=reply_to,
        )
        return

    await bot.send_photo(
        chat_id=chat_id,
        photo=url_result.value.url,
        caption=caption,
        reply_to_message_id=reply_to,
    )


async def send_response(
    bot: telegram.Bot,
    chat_id: int,
    response: NormalizedOutboundResponse,
    generate_access: GenerateAccess,
    actor: ActorScope,
) -> None:
    """Render a normalized response as one or more Telegram messages."""

    started = time.perf_counter()
    outcome = "success"
    try:
        reply_to = int(response.reply_to.message_id) if response.reply_to else None
        text = response.text

        if response.kind in {ResponseKind.PROPOSAL, ResponseKind.CONFIRMATION}:
            if text is None:
                raise TelegramDeliveryError(f"{response.kind.value} response requires text")
            markup = _approval_markup(response.approval_actions)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to,
                reply_markup=markup,
            )
            logger.info("telegram response delivered")
            return

        if response.kind == ResponseKind.ATTACHMENT:
            if not response.attachments:
                raise TelegramDeliveryError("attachment response requires attachments")
            for attachment in response.attachments:
                await _send_attachment(
                    bot, chat_id, attachment, text, reply_to, generate_access, actor
                )
            logger.info("telegram response delivered")
            return

        if text is None:
            raise TelegramDeliveryError(f"{response.kind.value} response requires text")

        await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to)

        for attachment in response.attachments:
            await _send_attachment(bot, chat_id, attachment, None, reply_to, generate_access, actor)

        logger.info("telegram response delivered")
    except Exception as exc:
        outcome = "error"
        logger.exception("telegram delivery failed", extra={"error_category": type(exc).__name__})
        raise
    finally:
        METRICS.provider_delivery.labels(provider="telegram", outcome=outcome).inc()
        METRICS.provider_delivery_latency.labels(provider="telegram").observe(
            time.perf_counter() - started
        )
