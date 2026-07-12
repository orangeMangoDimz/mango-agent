"""Map Discord SDK objects to provider-independent channel contracts."""

from __future__ import annotations

import discord

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    NormalizedInboundMessage,
    ReplyReference,
)
from mango_agent.shared.domain.value_objects import Timestamp


def _display_name(author: discord.User | discord.Member) -> str:
    if isinstance(author, discord.Member):
        return (author.nick or author.display_name or author.name).strip()
    return (author.display_name or author.name).strip()


def _thread_id(message: discord.Message) -> str | None:
    return str(message.thread.id) if message.thread else None


def build_normalized_message(
    bot_id: str,
    agent_command: str,
    message: discord.Message,
) -> NormalizedInboundMessage:
    """Convert a Discord message into a normalized inbound message."""

    thread_id = _thread_id(message)
    reply_to = None
    reference = message.reference
    if reference is not None and reference.message_id is not None:
        reply_to = ReplyReference(
            message_id=str(reference.message_id),
            conversation_id=str(message.channel.id),
            thread_id=thread_id,
        )

    return NormalizedInboundMessage(
        provider=Provider.DISCORD,
        bot_id=bot_id,
        agent_command=agent_command,
        provider_event_id=str(message.id),
        conversation_id=str(message.channel.id),
        thread_id=thread_id,
        provider_user_id=str(message.author.id),
        display_name=_display_name(message.author),
        username=message.author.name,
        message_id=str(message.id),
        text=message.content,
        attachments=(),
        reply_to=reply_to,
        received_at=Timestamp.now(),
    )
