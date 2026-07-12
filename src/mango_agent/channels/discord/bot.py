"""Discord gateway adapter that runs a configured agent."""

from __future__ import annotations

from typing import Any

import discord

from ._processor import DiscordMessageProcessor


class DiscordGateway(discord.Client):
    """Discord gateway boundary wiring a configured agent to message events."""

    def __init__(
        self,
        processor: DiscordMessageProcessor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._processor = processor

    async def on_message(self, message: discord.Message) -> None:
        await self._processor.process_message(message)
