"""Contract tests for the Discord channel boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, final

import pytest
from tests.unit.modules.identity.fakes import FakeIdentityUnitOfWork

from mango_agent.agents.contract import Agent
from mango_agent.channels.discord import DiscordMessageProcessor
from mango_agent.channels.discord._normalization import build_normalized_message
from mango_agent.modules.identity.application.use_cases import (
    AuthenticatedContext,
    ResolveProviderIdentity,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.channel_contracts import (
    NormalizedInboundMessage,
    NormalizedOutboundResponse,
)
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
class FakeIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._keys: set[IdempotencyKey] = set()

    async def claim_event(self, actor: ActorScope, key: IdempotencyKey) -> Any:
        if key in self._keys:
            return key
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


@dataclass
class FakeDiscordChannel:
    id: int = 789
    sent: list[str] = field(default_factory=list)

    async def send(self, content: str) -> None:
        self.sent.append(content)


@dataclass
class FakeDiscordAuthor:
    id: int = 456
    name: str = "alice"
    display_name: str = "Alice"
    bot: bool = False


@dataclass
class FakeDiscordReference:
    message_id: int | None = None


@dataclass
class FakeDiscordMessage:
    id: int = 100
    content: str = "hello"
    author: FakeDiscordAuthor = field(default_factory=FakeDiscordAuthor)
    channel: FakeDiscordChannel = field(default_factory=FakeDiscordChannel)
    reference: FakeDiscordReference | None = None
    thread: Any | None = None


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def uow() -> FakeIdentityUnitOfWork:
    return FakeIdentityUnitOfWork()


@pytest.fixture
def idempotency_repo() -> FakeIdempotencyRepository:
    return FakeIdempotencyRepository()


def _make_processor(
    agent: FakeAgent,
    uow: FakeIdentityUnitOfWork,
    idempotency_repo: FakeIdempotencyRepository,
) -> DiscordMessageProcessor:
    return DiscordMessageProcessor(
        bot_id="discord-bot",
        agent_command="task_management",
        agent=agent,
        resolve_identity=ResolveProviderIdentity(uow),
        idempotency_repo=idempotency_repo,
    )


async def test_discord_processor_routes_text_message_to_agent(
    agent: FakeAgent,
    uow: FakeIdentityUnitOfWork,
    idempotency_repo: FakeIdempotencyRepository,
) -> None:
    processor = _make_processor(agent, uow, idempotency_repo)
    message = FakeDiscordMessage(id=101, content="show my tasks")

    await processor.process_message(message)

    assert len(agent.requests) == 1
    request = agent.requests[0]
    assert request.provider == Provider.DISCORD
    assert request.bot_id == "discord-bot"
    assert request.agent_command == "task_management"
    assert request.provider_user_id == "456"
    assert request.text == "show my tasks"
    assert message.channel.sent[-1] == "Fake agent: show my tasks"


async def test_discord_normalization_preserves_thread_and_reply_reference() -> None:
    thread = FakeDiscordChannel(id=1000)
    message = FakeDiscordMessage(
        id=102,
        content="reply",
        channel=FakeDiscordChannel(id=200),
        reference=FakeDiscordReference(message_id=99),
        thread=thread,
    )

    normalized = build_normalized_message("discord-bot", "task_management", message)

    assert normalized.conversation_id == "200"
    assert normalized.thread_id == "1000"
    assert normalized.reply_to is not None
    assert normalized.reply_to.message_id == "99"


async def test_discord_processor_ignores_bot_messages(
    agent: FakeAgent,
    uow: FakeIdentityUnitOfWork,
    idempotency_repo: FakeIdempotencyRepository,
) -> None:
    processor = _make_processor(agent, uow, idempotency_repo)
    message = FakeDiscordMessage(author=FakeDiscordAuthor(bot=True))

    await processor.process_message(message)

    assert len(agent.requests) == 0
