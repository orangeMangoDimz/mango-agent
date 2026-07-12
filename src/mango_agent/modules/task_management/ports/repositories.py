"""Task management repository ports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from mango_agent.modules.task_management.domain.enums import Priority, Status
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.shared.domain.ids import ProjectId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination
from mango_agent.shared.ports.actor_scope import ActorScope

__all__ = [
    "ProjectRepository",
    "ProjectSearchQuery",
    "TaskRepository",
    "TaskSearchFilter",
]


@final
@dataclass(frozen=True, slots=True)
class ProjectSearchQuery:
    """Domain-specific search criteria for projects."""

    owner_user_id: UserId | None = None
    title_contains: str | None = None


@final
@dataclass(frozen=True, slots=True)
class TaskSearchFilter:
    """Domain-specific search criteria for tasks."""

    project_id: ProjectId | None = None
    status: Status | None = None
    priority: Priority | None = None
    title_contains: str | None = None
    tags: frozenset[str] | None = None


class ProjectRepository(ABC):
    """Port for persisting and querying projects."""

    @abstractmethod
    async def create(self, actor: ActorScope, project: Project) -> Project:
        """Persist a new project."""

    @abstractmethod
    async def get(self, actor: ActorScope, project_id: ProjectId) -> Project:
        """Return the project with the given id."""

    @abstractmethod
    async def search(
        self,
        actor: ActorScope,
        query: ProjectSearchQuery,
        pagination: Pagination,
    ) -> PaginatedResult[Project]:
        """Search projects scoped to the actor."""

    @abstractmethod
    async def update(self, actor: ActorScope, project: Project) -> Project:
        """Persist an updated project."""

    @abstractmethod
    async def delete(self, actor: ActorScope, project_id: ProjectId) -> None:
        """Delete the project with the given id."""


class TaskRepository(ABC):
    """Port for persisting and querying tasks."""

    @abstractmethod
    async def create(self, actor: ActorScope, task: Task) -> Task:
        """Persist a new task."""

    @abstractmethod
    async def get(self, actor: ActorScope, task_id: TaskId) -> Task:
        """Return the task with the given id."""

    @abstractmethod
    async def search(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> PaginatedResult[Task]:
        """Search tasks matching the criteria."""

    @abstractmethod
    async def update(self, actor: ActorScope, task: Task) -> Task:
        """Persist an updated task."""

    @abstractmethod
    async def delete(self, actor: ActorScope, task_id: TaskId) -> None:
        """Delete the task with the given id."""

    @abstractmethod
    async def transition_status(
        self,
        actor: ActorScope,
        task_id: TaskId,
        new_status: Status,
    ) -> Task:
        """Transition the task to the new status and persist it."""
