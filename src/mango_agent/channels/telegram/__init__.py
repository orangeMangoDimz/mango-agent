"""Telegram channel adapter."""

from __future__ import annotations

from mango_agent.channels.telegram._processor import TelegramMessageProcessor
from mango_agent.channels.telegram.bot import TelegramBot

__all__ = ["TelegramBot", "TelegramMessageProcessor"]
