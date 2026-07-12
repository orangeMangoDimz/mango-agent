"""Task management repository ports."""

from __future__ import annotations

from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)

__all__ = [
    "ProjectRepository",
    "ProjectSearchQuery",
    "TaskRepository",
    "TaskSearchFilter",
]
