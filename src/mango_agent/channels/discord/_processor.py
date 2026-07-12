"""Process Discord events into normalized agent requests and deliver responses."""

from __future__ import annotations

import contextlib
import time

import discord

from mango_agent.agents.contract import Agent
from mango_agent.modules.identity.application.use_cases import (
    AuthenticatedContext,
    ResolveProviderIdentity,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.ids import OperationId, UserId
from mango_agent.shared.infrastructure.correlation import correlation_id_scope
from mango_agent.shared.infrastructure.logging import log_context, logger
from mango_agent.shared.infrastructure.metrics import METRICS
from mango_agent.shared.ports.actor_scope import ActorScope
from mango_agent.shared.ports.idempotency import IdempotencyKey, IdempotencyRepository

from ._delivery import send_response
from ._normalization import build_normalized_message


class DiscordProcessorError(Exception):
    """Raised when a Discord event cannot be processed."""


class DiscordMessageProcessor:
    """Turn Discord messages into normalized requests, run the agent, and send results."""

    def __init__(
        self,
        bot_id: str,
        agent_command: str,
        agent: Agent,
        resolve_identity: ResolveProviderIdentity,
        idempotency_repo: IdempotencyRepository,
    ) -> None:
        self._bot_id = bot_id
        self._agent_command = agent_command
        self._agent = agent
        self._resolve_identity = resolve_identity
        self._idempotency_repo = idempotency_repo

    async def _resolve_user(self, author: discord.User | discord.Member) -> AuthenticatedContext:
        display_name = (author.display_name or author.name or "Discord User").strip()
        actor = ActorScope(
            user_id=UserId.generate(),
            bot_id=self._bot_id,
            command=self._agent_command,
        )
        result = await self._resolve_identity(
            actor,
            Provider.DISCORD,
            str(author.id),
            author.name,
            display_name,
        )
        if result.is_failure:
            raise DiscordProcessorError(result.error.message)
        return result.value

    def _actor(self, context: AuthenticatedContext) -> ActorScope:
        return ActorScope(
            user_id=context.internal_user_id,
            bot_id=context.bot_id,
            command=context.command,
        )

    async def process_message(self, message: discord.Message) -> None:
        """Handle an incoming Discord message."""

        if message.author.bot:
            return

        with correlation_id_scope():
            auth_context = await self._resolve_user(message.author)
            actor = self._actor(auth_context)
            event_key = IdempotencyKey.for_provider_event("discord", str(message.id))
            operation_id = await self._claim_event(actor, event_key)
            if operation_id is None:
                METRICS.duplicate_events.labels(kind="provider_event").inc()
                return

            with log_context(
                channel="discord",
                command=self._agent_command,
                bot_instance=self._bot_id,
                user_id=str(actor.user_id),
                operation_id=str(operation_id),
            ):
                started = time.perf_counter()
                outcome = "success"
                try:
                    logger.info("processing discord message")
                    normalized = build_normalized_message(
                        self._bot_id, self._agent_command, message
                    )
                    response = await self._agent.execute(auth_context, normalized)
                    await send_response(message.channel, response)
                    logger.info("discord message processed")
                except Exception as exc:
                    outcome = "error"
                    logger.exception(
                        "discord message failed",
                        extra={"error_category": type(exc).__name__},
                    )
                    with contextlib.suppress(Exception):
                        await message.channel.send(f"Sorry, I couldn't process that: {exc}")
                finally:
                    METRICS.messages.labels(
                        channel="discord",
                        command=self._agent_command,
                        outcome=outcome,
                    ).inc()
                    METRICS.message_latency.labels(
                        channel="discord",
                        command=self._agent_command,
                    ).observe(time.perf_counter() - started)
                    with contextlib.suppress(Exception):
                        await self._idempotency_repo.record_operation(
                            actor, event_key, operation_id
                        )

    async def _claim_event(self, actor: ActorScope, key: IdempotencyKey) -> OperationId | None:
        operation_id = OperationId.generate()
        existing = await self._idempotency_repo.claim_event(actor, key, operation_id)
        if existing is not None:
            return None
        return operation_id
