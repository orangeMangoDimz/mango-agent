"""Task entity."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from mango_agent.modules.task_management.domain.enums import Priority, Status
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import ProjectId, TaskId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


@final
@dataclass(frozen=True, slots=True)
class Task:
    id: TaskId
    project_id: ProjectId
    title: str
    description: str
    priority: Priority
    status: Status
    tags: frozenset[str]
    assigned_by: UserId | None
    assigned_to: UserId | None
    notes: tuple[Note, ...]
    created_at: Timestamp
    updated_at: Timestamp
    done_at: Timestamp | None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("task title must not be empty")
        if not isinstance(self.priority, Priority):
            raise ValidationError("priority must be a Priority value")
        if not isinstance(self.status, Status):
            raise ValidationError("status must be a Status value")

    @classmethod
    def create(
        cls,
        project_id: ProjectId,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        status: Status = Status.TODO,
        assigned_by: UserId | None = None,
        assigned_to: UserId | None = None,
        tags: frozenset[str] | None = None,
    ) -> Task:
        now = Timestamp.now()
        return cls(
            id=TaskId.generate(),
            project_id=project_id,
            title=title.strip(),
            description=description,
            priority=priority,
            status=status,
            tags=frozenset(tags) if tags else frozenset(),
            assigned_by=assigned_by,
            assigned_to=assigned_to,
            notes=(),
            created_at=now,
            updated_at=now,
            done_at=None,
        )

    def rename(self, title: str) -> Task:
        return replace(self, title=title.strip(), updated_at=Timestamp.now())

    def set_description(self, description: str) -> Task:
        return replace(self, description=description, updated_at=Timestamp.now())

    def set_priority(self, priority: Priority) -> Task:
        return replace(self, priority=priority, updated_at=Timestamp.now())

    def set_status(self, status: Status, now: Timestamp | None = None) -> Task:
        if not isinstance(status, Status):
            raise ValidationError("status must be a Status value")
        if now is None:
            now = Timestamp.now()
        if status == self.status:
            return replace(self, updated_at=now)

        done_at = self.done_at
        if status == Status.DONE:
            done_at = now
        elif self.status == Status.DONE:
            done_at = None

        return replace(self, status=status, updated_at=now, done_at=done_at)

    def assign(self, assigned_by: UserId | None, assigned_to: UserId | None) -> Task:
        return replace(self, 
            assigned_by=assigned_by,
            assigned_to=assigned_to,
            updated_at=Timestamp.now(),
        )

    def add_note(self, note: Note) -> Task:
        return replace(self, notes=self.notes + (note,), updated_at=Timestamp.now())

    def set_tags(self, tags: frozenset[str]) -> Task:
        return replace(self, tags=frozenset(tags), updated_at=Timestamp.now())
