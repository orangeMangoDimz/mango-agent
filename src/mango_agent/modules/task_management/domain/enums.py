"""Task management enumerations."""

from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class Status(StrEnum):
    TODO = "Todo"
    IN_PROGRESS = "In progress"
    BLOCKED = "Blocked"
    DONE = "Done"
    CANCELLED = "Cancelled"
