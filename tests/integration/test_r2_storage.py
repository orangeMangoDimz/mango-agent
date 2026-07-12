"""Integration tests for Cloudflare R2 attachment storage."""

from __future__ import annotations

import os
import uuid

import pytest

from mango_agent.modules.attachments.adapters.r2_storage import (
    R2AttachmentStorage,
    R2StorageConfig,
)
from mango_agent.modules.attachments.ports.storage import UploadRequest
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope

_R2_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)


def _credentials_present() -> bool:
    return all(os.environ.get(name) for name in _R2_ENV_VARS)


pytestmark = pytest.mark.skipif(
    not _credentials_present(),
    reason="R2 credentials not set; set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
    "R2_SECRET_ACCESS_KEY, and R2_BUCKET",
)


@pytest.fixture
async def storage() -> R2AttachmentStorage:
    config = R2StorageConfig(
        account_id=os.environ["R2_ACCOUNT_ID"],
        access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        bucket=os.environ["R2_BUCKET"],
    )
    return R2AttachmentStorage(config)


def _actor_scope() -> ActorScope:
    return ActorScope(user_id=UserId.generate(), bot_id="test-bot")


async def test_upload_retrieve_presign_delete(storage: R2AttachmentStorage) -> None:
    actor_scope = _actor_scope()
    unique_name = f"test-upload-{uuid.uuid4()}.png"
    content = b"fake-image-bytes"
    request = UploadRequest(
        content=content,
        original_filename=unique_name,
        mime_type="image/png",
        uploader_user_id=actor_scope.user_id,
    )

    key = await storage.upload(request)
    assert key.startswith(f"attachments/{actor_scope.user_id}/")
    assert key.endswith(unique_name)

    try:
        retrieved = await storage.retrieve(key)
        assert retrieved == content

        presigned = await storage.generate_presigned_url(key, actor_scope)
        assert presigned.url.startswith("https://")
        assert presigned.expires_at.value > Timestamp.now().value
    finally:
        await storage.delete(key)
        await storage.delete(key)


async def test_delete_missing_object_is_idempotent(storage: R2AttachmentStorage) -> None:
    await storage.delete("attachments/non-existent-object.png")


async def test_upload_invalid_mime_raises(storage: R2AttachmentStorage) -> None:
    request = UploadRequest(
        content=b"content",
        original_filename="image.gif",
        mime_type="image/gif",
        uploader_user_id=UserId.generate(),
    )
    with pytest.raises(ValidationError):
        await storage.upload(request)


async def test_upload_oversized_raises(storage: R2AttachmentStorage) -> None:
    oversized_content = b"x" * (10 * 1024 * 1024 + 1)
    request = UploadRequest(
        content=oversized_content,
        original_filename="image.png",
        mime_type="image/png",
        uploader_user_id=UserId.generate(),
    )
    with pytest.raises(ValidationError):
        await storage.upload(request)
