"""Contract tests for the Telegram channel adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import SimpleNamespace
from typing import Any, final

import pytest
from telegram import Chat, Message, PhotoSize, Update, User
from tests.unit.modules.identity.fakes import FakeIdentityUnitOfWork

from mango_agent.agents.contract import Agent
from mango_agent.channels.telegram import TelegramMessageProcessor
from mango_agent.channels.telegram._delivery import send_response
from mango_agent.modules.attachments.domain import (
    Attachment,
    AttachmentLifecycleStatus,
    StorageProvider,
)
from mango_agent.modules.attachments.ports.storage import (
    PresignedUrl,
    UploadRequest,
)
from mango_agent.modules.identity.application.use_cases import (
    AuthenticatedContext,
    ResolveProviderIdentity,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    ApprovalAction,
    ApprovalActionKind,
    AttachmentDescriptor,
    NormalizedInboundMessage,
    NormalizedOutboundResponse,
    ResponseKind,
)
from mango_agent.shared.domain.ids import AttachmentId, OperationId, UserId
from mango_agent.shared.domain.result import Result
from mango_agent.shared.domain.value_objects import Timestamp
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository


@final
class FakeAgent(Agent):
    def __init__(self) -> None:
        self.requests: list[NormalizedInboundMessage] = []

    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedInboundMessage,
    ) -> NormalizedOutboundResponse:
        self.requests.append(payload)
        return NormalizedOutboundResponse.final_text(f"Fake agent: {payload.text}")


@final
class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.sent_photos: list[dict[str, Any]] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: Any = None,
    ) -> None:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": reply_to_message_id,
                "reply_markup": reply_markup,
            }
        )

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        *,
        caption: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> None:
        self.sent_photos.append(
            {
                "chat_id": chat_id,
                "photo": photo,
                "caption": caption,
                "reply_to_message_id": reply_to_message_id,
            }
        )

    async def get_file(self, file_id: str) -> FakeFile:
        return FakeFile()


@final
class FakeFile:
    async def download_as_bytearray(self) -> bytearray:
        return bytearray(b"fake-image-data")


@final
class FakeRegisterPendingUpload:
    async def __call__(self, actor: ActorScope, request: UploadRequest) -> Result[Attachment, Any]:
        attachment = Attachment.create(
            uploader_user_id=actor.user_id,
            storage_provider=StorageProvider.R2,
            bucket_name="mango-attachments",
            object_key=f"uploads/{request.original_filename}",
            original_filename=request.original_filename,
            mime_type=request.mime_type,
            file_size=len(request.content),
        ).transition_to(AttachmentLifecycleStatus.UPLOADED)
        return Result.success(attachment)


@final
class FakeGenerateAccess:
    async def __call__(
        self, actor: ActorScope, attachment_id: AttachmentId, ttl_seconds: int = 300
    ) -> Result[PresignedUrl, Any]:
        return Result.success(
            PresignedUrl(
                url=f"https://r2.example/{attachment_id}",
                expires_at=Timestamp.now(),
            )
        )


@final
class FakeIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._keys: set[IdempotencyKey] = set()

    async def claim_event(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> OperationId | None:
        if key in self._keys:
            return operation_id
        self._keys.add(key)
        return None

    async def record_operation(
        self, actor: ActorScope, key: IdempotencyKey, operation_id: Any
    ) -> None:
        pass

    async def lookup_operation(self, actor: ActorScope, key: IdempotencyKey) -> Any:
        return None

    async def record_result(
        self, actor: ActorScope, key: IdempotencyKey, result_resource_id: Any
    ) -> None:
        pass

    async def lookup_result(self, actor: ActorScope, key: IdempotencyKey) -> Any:
        return None


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def uow() -> FakeIdentityUnitOfWork:
    return FakeIdentityUnitOfWork()


@pytest.fixture
def uow_factory(uow: FakeIdentityUnitOfWork) -> Callable[[], FakeIdentityUnitOfWork]:
    return lambda: uow


@pytest.fixture
def register_upload() -> FakeRegisterPendingUpload:
    return FakeRegisterPendingUpload()


@pytest.fixture
def generate_access() -> FakeGenerateAccess:
    return FakeGenerateAccess()


@pytest.fixture
def idempotency_repo() -> FakeIdempotencyRepository:
    return FakeIdempotencyRepository()


def _make_text_update(text: str, update_id: int = 1) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(),
            chat=Chat(id=123, type="private"),
            from_user=User(id=456, is_bot=False, first_name="Alice", username="alice"),
            text=text,
        ),
    )


def _make_photo_update(caption: str | None = None, update_id: int = 2) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(),
            chat=Chat(id=123, type="private"),
            from_user=User(id=456, is_bot=False, first_name="Alice", username="alice"),
            caption=caption,
            photo=(
                PhotoSize(
                    file_id="photo-1",
                    file_unique_id="unique-1",
                    width=100,
                    height=100,
                    file_size=1000,
                ),
            ),
        ),
    )


def _make_processor(
    agent: FakeAgent,
    uow_factory: Callable[[], FakeIdentityUnitOfWork],
    register_upload: FakeRegisterPendingUpload,
    generate_access: FakeGenerateAccess,
    idempotency_repo: FakeIdempotencyRepository,
) -> TelegramMessageProcessor:
    return TelegramMessageProcessor(
        bot_id="task-bot",
        agent_command="task_management",
        agent=agent,
        resolve_identity=ResolveProviderIdentity(uow_factory=uow_factory),
        register_upload=register_upload,
        generate_access=generate_access,
        idempotency_repo=idempotency_repo,
    )


async def test_telegram_processor_routes_text_message_to_agent(
    agent: FakeAgent,
    bot: FakeBot,
    uow_factory: Callable[[], FakeIdentityUnitOfWork],
    register_upload: FakeRegisterPendingUpload,
    generate_access: FakeGenerateAccess,
    idempotency_repo: FakeIdempotencyRepository,
) -> None:
    processor = _make_processor(
        agent, uow_factory, register_upload, generate_access, idempotency_repo
    )
    update = _make_text_update("create a task")
    context = SimpleNamespace(bot=bot)

    await processor.process_message(update, context)

    assert len(agent.requests) == 1
    request = agent.requests[0]
    assert request.provider == Provider.TELEGRAM
    assert request.bot_id == "task-bot"
    assert request.agent_command == "task_management"
    assert request.provider_user_id == "456"
    assert request.text == "create a task"
    assert request.conversation_id == "123"
    assert bot.sent_messages[-1]["text"] == "Fake agent: create a task"


async def test_telegram_processor_uploads_photo_and_routes_caption_to_agent(
    agent: FakeAgent,
    bot: FakeBot,
    uow_factory: Callable[[], FakeIdentityUnitOfWork],
    register_upload: FakeRegisterPendingUpload,
    generate_access: FakeGenerateAccess,
    idempotency_repo: FakeIdempotencyRepository,
) -> None:
    processor = _make_processor(
        agent, uow_factory, register_upload, generate_access, idempotency_repo
    )
    update = _make_photo_update(caption="from this image", update_id=3)
    context = SimpleNamespace(bot=bot)

    await processor.process_message(update, context)

    request = agent.requests[0]
    assert len(request.attachments) == 1
    assert request.attachments[0].media_type == "image"
    assert request.text == "from this image"


async def test_telegram_processor_skips_duplicate_updates(
    agent: FakeAgent,
    bot: FakeBot,
    uow_factory: Callable[[], FakeIdentityUnitOfWork],
    register_upload: FakeRegisterPendingUpload,
    generate_access: FakeGenerateAccess,
    idempotency_repo: FakeIdempotencyRepository,
) -> None:
    processor = _make_processor(
        agent, uow_factory, register_upload, generate_access, idempotency_repo
    )
    context = SimpleNamespace(bot=bot)

    await processor.process_message(_make_text_update("first", update_id=10), context)
    await processor.process_message(_make_text_update("second", update_id=10), context)

    assert len(agent.requests) == 1


async def test_telegram_delivery_renders_proposal_with_inline_keyboard(
    bot: FakeBot,
    generate_access: FakeGenerateAccess,
) -> None:
    operation_id = OperationId.generate()
    response = NormalizedOutboundResponse(
        kind=ResponseKind.PROPOSAL,
        text="Create the task?",
        operation_id=operation_id,
        approval_actions=(
            ApprovalAction(ApprovalActionKind.APPROVE, "Create", operation_id),
            ApprovalAction(ApprovalActionKind.REJECT, "Cancel", operation_id),
        ),
    )
    actor = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")

    await send_response(bot, 123, response, generate_access, actor)

    assert len(bot.sent_messages) == 1
    sent = bot.sent_messages[0]
    assert sent["text"] == "Create the task?"
    assert sent["reply_markup"] is not None


async def test_telegram_delivery_sends_attachment_with_presigned_url(
    bot: FakeBot,
    generate_access: FakeGenerateAccess,
) -> None:
    attachment_id = AttachmentId.generate()
    response = NormalizedOutboundResponse(
        kind=ResponseKind.ATTACHMENT,
        attachments=(
            AttachmentDescriptor(
                attachment_id=attachment_id,
                media_type="image",
            ),
        ),
    )
    actor = ActorScope(user_id=UserId.generate(), bot_id="bot", command="cmd")

    await send_response(bot, 123, response, generate_access, actor)

    assert len(bot.sent_photos) == 1
    assert bot.sent_photos[0]["photo"] == f"https://r2.example/{attachment_id}"
