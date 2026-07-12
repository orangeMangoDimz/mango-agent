"""Deliver provider-independent responses to Discord."""

from __future__ import annotations

import discord

from mango_agent.shared.channel_contracts import (
    NormalizedOutboundResponse,
    ResponseKind,
)
from mango_agent.shared.domain.errors import MangoError


class DiscordDeliveryError(MangoError):
    """Raised when a normalized response cannot be delivered to Discord."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="internal_error")


def _approval_text(response: NormalizedOutboundResponse) -> str:
    if response.text is None:
        raise DiscordDeliveryError(f"{response.kind.value} response requires text")
    lines = [response.text, "", "Actions:"]
    for action in response.approval_actions:
        lines.append(f"- {action.label}")
    return "\n".join(lines)


async def send_response(
    channel: discord.abc.Messageable,
    response: NormalizedOutboundResponse,
) -> None:
    """Render a normalized response as a Discord message."""

    if response.kind in {ResponseKind.PROPOSAL, ResponseKind.CONFIRMATION}:
        await channel.send(_approval_text(response))
        return

    text = response.text
    if text is None:
        raise DiscordDeliveryError(f"{response.kind.value} response requires text")

    await channel.send(text)
