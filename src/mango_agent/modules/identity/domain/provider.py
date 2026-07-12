"""Supported channel providers for identity resolution."""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
    """A provider that can supply a user identity."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
