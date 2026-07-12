"""Cloudflare R2 implementation of the attachment storage port."""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, final

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError

from mango_agent.modules.attachments.ports.storage import (
    DEFAULT_PRESIGNED_URL_TTL_SECONDS,
    AttachmentStorage,
    PresignedUrl,
    UploadRequest,
)
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.infrastructure.metrics import METRICS
from mango_agent.shared.ports.actor_scope import ActorScope

_ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
_DEFAULT_REGION = "auto"
_S3_SERVICE_NAME = "s3"
_KEY_PREFIX = "attachments"
_PATH_UNSAFE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")


@asynccontextmanager
async def _r2_metrics(operation: str) -> AsyncIterator[None]:
    started = time.perf_counter()
    try:
        yield
    except Exception:
        METRICS.r2_errors.labels(operation=operation).inc()
        raise
    finally:
        METRICS.r2_operations.labels(operation=operation).inc()
        METRICS.r2_latency.labels(operation=operation).observe(time.perf_counter() - started)


def _build_default_endpoint(account_id: str) -> str:
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _sanitize_filename(filename: str) -> str:
    safe = _PATH_UNSAFE_PATTERN.sub("_", filename.strip())
    safe = safe.strip("._")
    if not safe:
        return "attachment"
    return safe


def _make_object_key(
    user_id: str,
    attachment_id: AttachmentId,
    original_filename: str,
) -> str:
    safe_name = _sanitize_filename(original_filename)
    return f"{_KEY_PREFIX}/{user_id}/{attachment_id}/{safe_name}"


@final
@dataclass(frozen=True, slots=True)
class R2StorageConfig:
    """Credentials and bucket for the R2 S3-compatible API."""

    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint_url: str | None = None


@final
class R2AttachmentStorage(AttachmentStorage):
    """Private R2 object storage with short-lived presigned retrieval URLs."""

    def __init__(self, config: R2StorageConfig) -> None:
        self._config = config
        self._endpoint_url = config.endpoint_url or _build_default_endpoint(config.account_id)

    @asynccontextmanager
    async def _client(self) -> Any:
        session = AioSession()
        async with session.create_client(
            _S3_SERVICE_NAME,
            region_name=_DEFAULT_REGION,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._config.access_key_id,
            aws_secret_access_key=self._config.secret_access_key,
        ) as client:
            yield client

    async def upload(self, request: UploadRequest) -> str:
        if request.mime_type not in _ALLOWED_MIME_TYPES:
            raise ValidationError(
                f"Unsupported MIME type: {request.mime_type}; "
                "must be image/jpeg, image/png, or image/webp"
            )
        if len(request.content) > _MAX_FILE_SIZE_BYTES:
            raise ValidationError("Attachment exceeds 10 MiB limit")

        attachment_id = AttachmentId.generate()
        object_key = _make_object_key(
            str(request.uploader_user_id),
            attachment_id,
            request.original_filename,
        )

        async with _r2_metrics("upload"), self._client() as client:
            await client.put_object(
                Bucket=self._config.bucket,
                Key=object_key,
                Body=request.content,
                ContentType=request.mime_type,
                Metadata={
                    "original_filename": request.original_filename,
                    "uploader_user_id": str(request.uploader_user_id),
                },
            )

        return object_key

    async def delete(self, object_key: str) -> None:
        async with _r2_metrics("delete"), self._client() as client:
            try:
                await client.delete_object(Bucket=self._config.bucket, Key=object_key)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "Unknown")
                if error_code != "NoSuchKey":
                    raise

    async def generate_presigned_url(
        self,
        object_key: str,
        actor_scope: ActorScope,
        ttl_seconds: int = DEFAULT_PRESIGNED_URL_TTL_SECONDS,
    ) -> PresignedUrl:
        async with _r2_metrics("generate_presigned_url"), self._client() as client:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": object_key},
                ExpiresIn=ttl_seconds,
            )

        expires_at = Timestamp.from_datetime(Timestamp.now().value + timedelta(seconds=ttl_seconds))
        return PresignedUrl(url=url, expires_at=expires_at)

    async def retrieve(self, object_key: str) -> bytes:
        async with _r2_metrics("retrieve"), self._client() as client:
            response = await client.get_object(Bucket=self._config.bucket, Key=object_key)
            async with response["Body"] as stream:
                data: bytes = await stream.read()
                return data
