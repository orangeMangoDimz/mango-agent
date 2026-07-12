"""Deliver provider-independent responses to Discord."""

from __future__ import annotations

import time

import discord

from mango_agent.shared.channel_contracts import (
    NormalizedOutboundResponse,
    ResponseKind,
)
from mango_agent.shared.domain.errors import MangoError
from mango_agent.shared.infrastructure.logging import logger
from mango_agent.shared.infrastructure.metrics import METRICS


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

    started = time.perf_counter()
    outcome = "success"
    try:
        if response.kind in {ResponseKind.PROPOSAL, ResponseKind.CONFIRMATION}:
            await channel.send(_approval_text(response))
            logger.info("discord response delivered")
            return

        text = response.text
        if text is None:
            raise DiscordDeliveryError(f"{response.kind.value} response requires text")

        await channel.send(text)
        logger.info("discord response delivered")
    except Exception as exc:
        outcome = "error"
        logger.exception("discord delivery failed", extra={"error_category": type(exc).__name__})
        raise
    finally:
        METRICS.provider_delivery.labels(provider="discord", outcome=outcome).inc()
        METRICS.provider_delivery_latency.labels(provider="discord").observe(
            time.perf_counter() - started
        )
