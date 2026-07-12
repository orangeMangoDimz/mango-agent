"""PostgreSQL implementations of task-management repository ports."""

from __future__ import annotations

import asyncpg
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError

from mango_agent.modules.task_management.domain.enums import Priority, Status
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports.repositories import (
    ProjectRepository,
    ProjectSearchQuery,
    TaskRepository,
    TaskSearchFilter,
)
from mango_agent.shared.domain.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from mango_agent.shared.domain.ids import ProjectId, TaskId, UserId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope


def _project_from_row(row: asyncpg.Record) -> Project:
    return Project(
        id=ProjectId.from_string(str(row["id"])),
        owner_user_id=UserId.from_string(str(row["owner_user_id"])),
        title=row["title"],
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
    )


def _note_text(notes: tuple[Note, ...]) -> str | None:
    return notes[0].user_text if notes else None


def _task_from_row(row: asyncpg.Record) -> Task:
    note_text = row["note"]
    notes = (Note(user_text=note_text),) if note_text else ()
    return Task(
        id=TaskId.from_string(str(row["id"])),
        project_id=ProjectId.from_string(str(row["project_id"])),
        title=row["title"],
        description=row["description"] or "",
        priority=Priority(row["priority"]),
        status=Status(row["status"]),
        tags=frozenset(row["tags"] or []),
        assigned_by=UserId.from_string(str(row["assigned_by_user_id"]))
        if row["assigned_by_user_id"]
        else None,
        assigned_to=UserId.from_string(str(row["assigned_to_user_id"]))
        if row["assigned_to_user_id"]
        else None,
        notes=notes,
        created_at=Timestamp.from_datetime(row["created_at"]),
        updated_at=Timestamp.from_datetime(row["updated_at"]),
        done_at=Timestamp.from_datetime(row["done_at"]) if row["done_at"] else None,
    )


class PostgresProjectRepository(ProjectRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create(self, actor: ActorScope, project: Project) -> Project:
        try:
            await self._connection.execute(
                "INSERT INTO projects (id, owner_user_id, title, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5)",
                project.id.value,
                project.owner_user_id.value,
                project.title,
                project.created_at.value,
                project.updated_at.value,
            )
        except UniqueViolationError as exc:
            raise ConflictError("project id already exists") from exc
        except ForeignKeyViolationError as exc:
            raise ValidationError("owner user does not exist") from exc
        return project

    async def get(self, actor: ActorScope, project_id: ProjectId) -> Project:
        row = await self._connection.fetchrow(
            "SELECT id, owner_user_id, title, created_at, updated_at FROM projects "
            "WHERE id = $1 AND owner_user_id = $2 AND deleted_at IS NULL",
            project_id.value,
            actor.user_id.value,
        )
        if row is None:
            raise NotFoundError("project not found")
        return _project_from_row(row)

    async def search(
        self,
        actor: ActorScope,
        query: ProjectSearchQuery,
        pagination: Pagination,
    ) -> PaginatedResult[Project]:
        filters = ["owner_user_id = $1", "deleted_at IS NULL"]
        params: list[object] = [actor.user_id.value]

        if query.title_contains:
            filters.append(f"title ILIKE ${len(params) + 1}")
            params.append(f"%{query.title_contains}%")

        where_clause = " AND ".join(filters)
        count_row = await self._connection.fetchrow(
            f"SELECT COUNT(*) FROM projects WHERE {where_clause}",
            *params,
        )
        total = count_row["count"] if count_row else 0

        params.extend([pagination.limit, pagination.offset])
        rows = await self._connection.fetch(
            f"SELECT id, owner_user_id, title, created_at, updated_at "
            f"FROM projects WHERE {where_clause} "
            f"ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return PaginatedResult(
            items=tuple(_project_from_row(row) for row in rows),
            total=total,
            pagination=pagination,
        )

    async def update(self, actor: ActorScope, project: Project) -> Project:
        result = await self._connection.execute(
            "UPDATE projects SET title = $1, updated_at = $2 "
            "WHERE id = $3 AND owner_user_id = $4 AND deleted_at IS NULL",
            project.title,
            project.updated_at.value,
            project.id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("project not found")
        return project

    async def delete(self, actor: ActorScope, project_id: ProjectId) -> None:
        result = await self._connection.execute(
            "UPDATE projects SET deleted_at = $1 "
            "WHERE id = $2 AND owner_user_id = $3 AND deleted_at IS NULL",
            Timestamp.now().value,
            project_id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("project not found")


class PostgresTaskRepository(TaskRepository):
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create(self, actor: ActorScope, task: Task) -> Task:
        try:
            await self._connection.execute(
                "INSERT INTO tasks (id, project_id, title, description, priority, status, "
                "tags, assigned_by_user_id, assigned_to_user_id, note, created_at, "
                "updated_at, done_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)",
                task.id.value,
                task.project_id.value,
                task.title,
                task.description,
                task.priority.value,
                task.status.value,
                list(task.tags),
                task.assigned_by.value if task.assigned_by else None,
                task.assigned_to.value if task.assigned_to else None,
                _note_text(task.notes),
                task.created_at.value,
                task.updated_at.value,
                task.done_at.value if task.done_at else None,
            )
        except UniqueViolationError as exc:
            raise ConflictError("task id already exists") from exc
        except ForeignKeyViolationError as exc:
            raise ValidationError("project does not exist") from exc
        return task

    async def get(self, actor: ActorScope, task_id: TaskId) -> Task:
        row = await self._connection.fetchrow(
            "SELECT t.* FROM tasks t "
            "JOIN projects p ON p.id = t.project_id "
            "WHERE t.id = $1 AND t.deleted_at IS NULL AND p.deleted_at IS NULL "
            "AND (p.owner_user_id = $2 OR t.assigned_to_user_id = $2 "
            "OR t.assigned_by_user_id = $2)",
            task_id.value,
            actor.user_id.value,
        )
        if row is None:
            raise NotFoundError("task not found")
        return _task_from_row(row)

    async def search(
        self,
        actor: ActorScope,
        criteria: TaskSearchFilter,
        pagination: Pagination,
    ) -> PaginatedResult[Task]:
        filters = [
            "(p.owner_user_id = $1 OR t.assigned_to_user_id = $1 OR t.assigned_by_user_id = $1)",
            "t.deleted_at IS NULL",
            "p.deleted_at IS NULL",
        ]
        params: list[object] = [actor.user_id.value]

        if criteria.project_id is not None:
            filters.append(f"t.project_id = ${len(params) + 1}")
            params.append(criteria.project_id.value)
        if criteria.status is not None:
            filters.append(f"t.status = ${len(params) + 1}")
            params.append(criteria.status.value)
        if criteria.priority is not None:
            filters.append(f"t.priority = ${len(params) + 1}")
            params.append(criteria.priority.value)
        if criteria.title_contains:
            filters.append(f"t.title ILIKE ${len(params) + 1}")
            params.append(f"%{criteria.title_contains}%")
        if criteria.tags:
            filters.append(f"t.tags && ${len(params) + 1}")
            params.append(list(criteria.tags))

        where_clause = " AND ".join(filters)
        count_row = await self._connection.fetchrow(
            f"SELECT COUNT(*) FROM tasks t "
            f"JOIN projects p ON p.id = t.project_id WHERE {where_clause}",
            *params,
        )
        total = count_row["count"] if count_row else 0

        params.extend([pagination.limit, pagination.offset])
        rows = await self._connection.fetch(
            f"SELECT t.* FROM tasks t "
            f"JOIN projects p ON p.id = t.project_id "
            f"WHERE {where_clause} "
            f"ORDER BY t.created_at DESC "
            f"LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return PaginatedResult(
            items=tuple(_task_from_row(row) for row in rows),
            total=total,
            pagination=pagination,
        )

    async def update(self, actor: ActorScope, task: Task) -> Task:
        result = await self._connection.execute(
            "UPDATE tasks SET title = $1, description = $2, priority = $3, status = $4, "
            "tags = $5, assigned_by_user_id = $6, assigned_to_user_id = $7, "
            "note = $8, updated_at = $9, done_at = $10 "
            "WHERE id = $11 AND deleted_at IS NULL "
            "AND EXISTS (SELECT 1 FROM projects p WHERE p.id = tasks.project_id "
            "AND p.owner_user_id = $12 AND p.deleted_at IS NULL)",
            task.title,
            task.description,
            task.priority.value,
            task.status.value,
            list(task.tags),
            task.assigned_by.value if task.assigned_by else None,
            task.assigned_to.value if task.assigned_to else None,
            _note_text(task.notes),
            task.updated_at.value,
            task.done_at.value if task.done_at else None,
            task.id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("task not found")
        return task

    async def delete(self, actor: ActorScope, task_id: TaskId) -> None:
        result = await self._connection.execute(
            "UPDATE tasks SET deleted_at = $1 "
            "WHERE id = $2 AND deleted_at IS NULL "
            "AND EXISTS (SELECT 1 FROM projects p WHERE p.id = tasks.project_id "
            "AND p.owner_user_id = $3 AND p.deleted_at IS NULL)",
            Timestamp.now().value,
            task_id.value,
            actor.user_id.value,
        )
        if result == "UPDATE 0":
            raise NotFoundError("task not found")

    async def transition_status(
        self,
        actor: ActorScope,
        task_id: TaskId,
        new_status: Status,
    ) -> Task:
        task = await self.get(actor, task_id)
        updated = task.set_status(new_status)
        return await self.update(actor, updated)
