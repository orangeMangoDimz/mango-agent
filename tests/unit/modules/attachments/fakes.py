"""Fakes for attachment use-case unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import final

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
)
from mango_agent.modules.attachments.ports import (
    AttachmentRepository,
    AttachmentStorage,
    PresignedUrl,
    UploadRequest,
)
from mango_agent.modules.task_management.domain.enums import Status
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports import TaskRepository
from mango_agent.shared.domain.errors import (
    InternalError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mango_agent.shared.domain.ids import AttachmentId, ProjectId, TaskId
from mango_agent.shared.domain.value_objects import PaginatedResult, Pagination, Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.unit_of_work import UnitOfWork


@final
class FakeAttachmentStorage(AttachmentStorage):
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._deleted_keys: list[str] = []
        self._generated_urls: list[PresignedUrl] = []

    async def upload(self, request: UploadRequest) -> str:
        if request.mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValidationError(f"Unsupported MIME type: {request.mime_type}")
        if len(request.content) > 10 * 1024 * 1024:
            raise ValidationError("Attachment exceeds 10 MiB limit")
        attachment_id = AttachmentId.generate()
        object_key = (
            f"attachments/{request.uploader_user_id}/{attachment_id}/{request.original_filename}"
        )
        self._objects[object_key] = request.content
        return object_key

    async def delete(self, object_key: str) -> None:
        if object_key in self._objects:
            self._deleted_keys.append(object_key)
            del self._objects[object_key]

    async def generate_presigned_url(
        self,
        object_key: str,
        actor_scope: ActorScope,
        ttl_seconds: int = 300,
    ) -> PresignedUrl:
        if object_key not in self._objects:
            raise NotFoundError(f"object {object_key} not found")
        expires_at = Timestamp.from_datetime(Timestamp.now().value + timedelta(seconds=ttl_seconds))
        url = PresignedUrl(
            url=f"https://fake.storage/{object_key}?ttl={ttl_seconds}",
            expires_at=expires_at,
        )
        self._generated_urls.append(url)
        return url

    async def retrieve(self, object_key: str) -> bytes:
        if object_key not in self._objects:
            raise NotFoundError(f"object {object_key} not found")
        return self._objects[object_key]

    def has_object(self, object_key: str) -> bool:
        return object_key in self._objects

    def was_deleted(self, object_key: str) -> bool:
        return object_key in self._deleted_keys


@final
@dataclass
class FakeAttachmentRepository(AttachmentRepository):
    task_repo: TaskRepository | None = None
    _attachments: dict[AttachmentId, Attachment] = field(default_factory=dict)
    _fail_next_register: bool = False

    def fail_next_register_pending(self) -> None:
        self._fail_next_register = True

    async def register_pending(self, actor: ActorScope, attachment: Attachment) -> Attachment:
        if self._fail_next_register:
            self._fail_next_register = False
            raise InternalError("simulated persistence failure")
        self._attachments[attachment.id] = attachment
        return attachment

    async def link_to_task(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        task_id: TaskId,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        linked = attachment.attach_to(task_id)
        self._attachments[attachment_id] = linked
        return linked

    async def get_authorized(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
    ) -> Attachment:
        attachment = self._attachments.get(attachment_id)
        if attachment is None:
            raise NotFoundError(f"attachment {attachment_id} not found")
        if attachment.uploader_user_id == actor.user_id:
            return attachment
        if await self._actor_authorized_for_task(actor, attachment):
            return attachment
        raise UnauthorizedError("not authorized to access attachment")

    async def _actor_authorized_for_task(
        self,
        actor: ActorScope,
        attachment: Attachment,
    ) -> bool:
        if self.task_repo is None or attachment.task_id is None:
            return False
        try:
            await self.task_repo.get(actor, attachment.task_id)
        except Exception:
            return False
        return True

    async def list_by_task(
        self,
        actor: ActorScope,
        task_id: TaskId,
        pagination: Pagination,
    ) -> PaginatedResult[Attachment]:
        items = tuple(a for a in self._attachments.values() if a.task_id == task_id)
        page = items[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResult(page, len(items), pagination)

    async def mark_lifecycle(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        new_status: AttachmentLifecycleStatus,
    ) -> Attachment:
        attachment = await self.get_authorized(actor, attachment_id)
        updated = attachment.transition_to(new_status)
        self._attachments[attachment_id] = updated
        return updated


@final
@dataclass
class FakeTaskRepository(TaskRepository):
    _projects: dict[ProjectId, Project] = field(default_factory=dict)
    _tasks: dict[TaskId, Task] = field(default_factory=dict)

    def add_project(self, project: Project) -> None:
        self._projects[project.id] = project

    def add_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def create(self, actor: ActorScope, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    async def get(self, actor: ActorScope, task_id: TaskId) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError(f"task {task_id} not found")
        project = self._projects.get(task.project_id)
        if project is None:
            raise NotFoundError(f"project for task {task_id} not found")
        if not self._actor_may_access_task(actor, task, project):
            raise UnauthorizedError("not authorized to access task")
        return task

    def _actor_may_access_task(
        self,
        actor: ActorScope,
        task: Task,
        project: Project,
    ) -> bool:
        if project.owner_user_id == actor.user_id:
            return True
        if task.assigned_to == actor.user_id:
            return True
        return task.assigned_by == actor.user_id

    async def search(
        self,
        actor: ActorScope,
        criteria: object,
        pagination: Pagination,
    ) -> PaginatedResult[Task]:
        accessible = [
            task
            for task in self._tasks.values()
            if self._actor_may_access_task(actor, task, self._projects[task.project_id])
        ]
        page = tuple(accessible[pagination.offset : pagination.offset + pagination.limit])
        return PaginatedResult(page, len(accessible), pagination)

    async def update(self, actor: ActorScope, task: Task) -> Task:
        if task.id not in self._tasks:
            raise NotFoundError(f"task {task.id} not found")
        await self.get(actor, task.id)
        self._tasks[task.id] = task
        return task

    async def delete(self, actor: ActorScope, task_id: TaskId) -> None:
        await self.get(actor, task_id)
        del self._tasks[task_id]

    async def transition_status(
        self,
        actor: ActorScope,
        task_id: TaskId,
        new_status: Status,
    ) -> Task:
        task = await self.get(actor, task_id)
        updated = task.set_status(new_status)
        self._tasks[task_id] = updated
        return updated


class FakeUnitOfWork(UnitOfWork):
    def __init__(
        self,
        attachment_repository: FakeAttachmentRepository | None = None,
        task_repository: FakeTaskRepository | None = None,
    ) -> None:
        self.attachments = attachment_repository or FakeAttachmentRepository()
        self.tasks = task_repository or FakeTaskRepository()
        self.begun = False
        self.committed = False
        self.rolled_back = False

    async def begin(self) -> None:
        self.begun = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
