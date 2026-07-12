"""Discord channel boundary."""

from __future__ import annotations

from mango_agent.channels.discord._processor import DiscordMessageProcessor
from mango_agent.channels.discord.bot import DiscordGateway

__all__ = ["DiscordGateway", "DiscordMessageProcessor"]
