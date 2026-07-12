from __future__ import annotations

import dataclasses
import inspect

import pytest

from mango_agent.modules.attachments.ports import (
    AttachmentStorage,
    PresignedUrl,
    UploadRequest,
)
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope


def _sample_request() -> UploadRequest:
    return UploadRequest(
        content=b"content",
        original_filename="image.png",
        mime_type="image/png",
        uploader_user_id=UserId.generate(),
    )


def test_upload_request_create() -> None:
    request = _sample_request()
    assert request.content == b"content"
    assert request.original_filename == "image.png"
    assert request.mime_type == "image/png"
    assert isinstance(request.uploader_user_id, UserId)


def test_upload_request_empty_filename_raises() -> None:
    with pytest.raises(ValidationError):
        UploadRequest(
            content=b"content",
            original_filename="   ",
            mime_type="image/png",
            uploader_user_id=UserId.generate(),
        )


def test_upload_request_empty_mime_type_raises() -> None:
    with pytest.raises(ValidationError):
        UploadRequest(
            content=b"content",
            original_filename="image.png",
            mime_type="   ",
            uploader_user_id=UserId.generate(),
        )


def test_upload_request_invalid_user_id_raises() -> None:
    with pytest.raises(ValidationError):
        UploadRequest(
            content=b"content",
            original_filename="image.png",
            mime_type="image/png",
            uploader_user_id="not-a-user-id",  # type: ignore[arg-type]
        )


def test_upload_request_is_frozen() -> None:
    request = _sample_request()
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.content = b"changed"


def test_presigned_url_create() -> None:
    expires = Timestamp.now()
    url = PresignedUrl(url="https://example.com/abc", expires_at=expires)
    assert url.url == "https://example.com/abc"
    assert url.expires_at == expires


def test_presigned_url_empty_url_raises() -> None:
    with pytest.raises(ValidationError):
        PresignedUrl(url="   ", expires_at=Timestamp.now())


def test_presigned_url_is_frozen() -> None:
    url = PresignedUrl(url="https://example.com/abc", expires_at=Timestamp.now())
    with pytest.raises(dataclasses.FrozenInstanceError):
        url.url = "https://example.com/def"


def test_attachment_storage_is_abstract() -> None:
    assert inspect.isabstract(AttachmentStorage)
    with pytest.raises(TypeError):
        AttachmentStorage()


def test_attachment_storage_methods_are_abstract() -> None:
    for method in (
        AttachmentStorage.upload,
        AttachmentStorage.delete,
        AttachmentStorage.generate_presigned_url,
        AttachmentStorage.retrieve,
    ):
        assert getattr(method, "__isabstractmethod__", False)


def test_generate_presigned_url_default_ttl() -> None:
    params = inspect.signature(AttachmentStorage.generate_presigned_url).parameters
    assert params["ttl_seconds"].default == 300


class _StubStorage(AttachmentStorage):
    async def upload(self, request: UploadRequest) -> str:
        return "stub-key"

    async def delete(self, object_key: str) -> None:
        return None

    async def generate_presigned_url(
        self,
        object_key: str,
        actor_scope: ActorScope,
        ttl_seconds: int = 300,
    ) -> PresignedUrl:
        return PresignedUrl(url="https://example.com/stub-key", expires_at=Timestamp.now())

    async def retrieve(self, object_key: str) -> bytes:
        return b""


def test_attachment_storage_can_be_implemented() -> None:
    storage = _StubStorage()
    assert isinstance(storage, AttachmentStorage)
