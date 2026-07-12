"""Attachment application use cases."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import final

from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.modules.attachments.ports import (
    AttachmentRepository,
    AttachmentStorage,
    PresignedUrl,
    UploadRequest,
)
from mango_agent.modules.task_management.ports.repositories import TaskRepository
from mango_agent.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InternalError,
    MangoError,
    ValidationError,
)
from mango_agent.shared.domain.ids import AttachmentId, TaskId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.ports.actor_scope import ActorScope

SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_BUCKET_NAME = "mango-attachments"


def _validate_upload_request(request: UploadRequest) -> ValidationError | None:
    if request.mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        return ValidationError(
            f"Unsupported MIME type: {request.mime_type}; "
            "must be image/jpeg, image/png, or image/webp"
        )
    if len(request.content) > MAX_FILE_SIZE_BYTES:
        return ValidationError("Attachment exceeds 10 MiB limit")
    return None


@final
@dataclass(frozen=True, slots=True)
class RegisterPendingUpload:
    _repository: AttachmentRepository
    _storage: AttachmentStorage
    _bucket_name: str = DEFAULT_BUCKET_NAME

    async def __call__(
        self,
        actor: ActorScope,
        request: UploadRequest,
    ) -> Result[Attachment, MangoError]:
        if actor.user_id != request.uploader_user_id:
            return Result.failure(
                ForbiddenError("actor does not match attachment uploader")
            )

        validation_error = _validate_upload_request(request)
        if validation_error is not None:
            return Result.failure(validation_error)

        try:
            object_key = await self._storage.upload(request)
        except ValidationError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(f"storage upload failed: {exc}"))

        attachment = Attachment.create(
            uploader_user_id=request.uploader_user_id,
            storage_provider=StorageProvider.R2,
            bucket_name=self._bucket_name,
            object_key=object_key,
            original_filename=request.original_filename,
            mime_type=request.mime_type,
            file_size=len(request.content),
        ).transition_to(AttachmentLifecycleStatus.UPLOADED)

        try:
            stored = await self._repository.register_pending(actor, attachment)
        except MangoError as exc:
            return await self._compensate(actor, object_key, attachment, exc)
        except Exception as exc:
            return await self._compensate(
                actor, object_key, attachment, InternalError(str(exc))
            )
        return Result.success(stored)

    async def _compensate(
        self,
        actor: ActorScope,
        object_key: str,
        attachment: Attachment,
        original_error: MangoError,
    ) -> Result[Attachment, MangoError]:
        try:
            await self._storage.delete(object_key)
        except Exception:
            orphan = attachment.transition_to(AttachmentLifecycleStatus.ORPHANED)
            with suppress(Exception):
                await self._repository.register_pending(actor, orphan)
            return Result.failure(
                InternalError(
                    f"upload failed and orphaned object remains: {original_error.message}"
                )
            )
        return Result.failure(
            InternalError(
                f"upload rolled back due to persistence failure: {original_error.message}"
            )
        )


@final
@dataclass(frozen=True, slots=True)
class LinkAttachmentToTask:
    _repository: AttachmentRepository
    _task_repository: TaskRepository

    async def __call__(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        task_id: TaskId,
    ) -> Result[Attachment, MangoError]:
        try:
            await self._repository.get_authorized(actor, attachment_id)
        except MangoError as exc:
            return Result.failure(exc)

        try:
            await self._task_repository.get(actor, task_id)
        except MangoError as exc:
            return Result.failure(
                ForbiddenError(f"not authorized to access task: {exc.message}")
            )

        try:
            linked = await self._repository.link_to_task(actor, attachment_id, task_id)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(f"failed to link attachment: {exc}"))
        return Result.success(linked)


@final
@dataclass(frozen=True, slots=True)
class AuthorizeRetrieval:
    _repository: AttachmentRepository

    async def __call__(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
    ) -> Result[Attachment, MangoError]:
        try:
            attachment = await self._repository.get_authorized(actor, attachment_id)
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(f"failed to retrieve attachment: {exc}"))
        return Result.success(attachment)


@final
@dataclass(frozen=True, slots=True)
class GenerateAccess:
    _repository: AttachmentRepository
    _storage: AttachmentStorage

    async def __call__(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
        ttl_seconds: int = 300,
    ) -> Result[PresignedUrl, MangoError]:
        authorized = await AuthorizeRetrieval(self._repository)(actor, attachment_id)
        if authorized.is_failure:
            return Result.failure(authorized.error)

        attachment = authorized.value
        try:
            url = await self._storage.generate_presigned_url(
                attachment.object_key, actor, ttl_seconds
            )
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(f"failed to generate presigned url: {exc}"))
        return Result.success(url)


@final
@dataclass(frozen=True, slots=True)
class RejectOrExpireAttachment:
    _repository: AttachmentRepository
    _storage: AttachmentStorage

    async def __call__(
        self,
        actor: ActorScope,
        attachment_id: AttachmentId,
    ) -> Result[Attachment, MangoError]:
        try:
            attachment = await self._repository.get_authorized(actor, attachment_id)
        except MangoError as exc:
            return Result.failure(exc)

        try:
            target_status = _resolve_reject_or_expire_status(attachment)
        except ConflictError as exc:
            return Result.failure(exc)

        if target_status == attachment.lifecycle_status:
            return Result.success(attachment)

        try:
            updated = await self._repository.mark_lifecycle(
                actor, attachment_id, target_status
            )
        except MangoError as exc:
            return Result.failure(exc)
        except Exception as exc:
            return Result.failure(InternalError(f"failed to update attachment status: {exc}"))

        if updated.lifecycle_status == AttachmentLifecycleStatus.CLEANUP_PENDING:
            with suppress(Exception):
                await self._storage.delete(updated.object_key)

        return Result.success(updated)


def _resolve_reject_or_expire_status(
    attachment: Attachment,
) -> AttachmentLifecycleStatus:
    status = attachment.lifecycle_status
    if status in {
        AttachmentLifecycleStatus.RECEIVED,
        AttachmentLifecycleStatus.UPLOADED,
        AttachmentLifecycleStatus.PENDING_METADATA,
    }:
        return AttachmentLifecycleStatus.REJECTED
    if status == AttachmentLifecycleStatus.ATTACHED:
        return AttachmentLifecycleStatus.CLEANUP_PENDING
    if status in {
        AttachmentLifecycleStatus.ORPHANED,
        AttachmentLifecycleStatus.EXPIRED,
        AttachmentLifecycleStatus.REJECTED,
        AttachmentLifecycleStatus.REJECTED_BY_VALIDATION,
        AttachmentLifecycleStatus.CLEANUP_PENDING,
    }:
        return status
    if status == AttachmentLifecycleStatus.DELETED:
        raise ConflictError("cannot reject or expire a deleted attachment")
    raise ConflictError(f"unexpected attachment status: {status.value}")
