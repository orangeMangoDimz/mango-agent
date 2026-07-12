"""Process Telegram updates into normalized agent requests and deliver responses."""

from __future__ import annotations

import contextlib
import time
from typing import Any

import telegram
from telegram import Update, User

from mango_agent.agents.contract import Agent
from mango_agent.modules.attachments.application.use_cases import (
    GenerateAccess,
    RegisterPendingUpload,
)
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
from ._normalization import (
    build_normalized_callback,
    build_normalized_message,
    upload_message_attachments,
)


class TelegramProcessorError(Exception):
    """Raised when a Telegram update cannot be processed."""


class TelegramMessageProcessor:
    """Turn Telegram updates into normalized requests, run the agent, and send results."""

    def __init__(
        self,
        bot_id: str,
        agent_command: str,
        agent: Agent,
        resolve_identity: ResolveProviderIdentity,
        register_upload: RegisterPendingUpload,
        generate_access: GenerateAccess,
        idempotency_repo: IdempotencyRepository,
    ) -> None:
        self._bot_id = bot_id
        self._agent_command = agent_command
        self._agent = agent
        self._resolve_identity = resolve_identity
        self._register_upload = register_upload
        self._generate_access = generate_access
        self._idempotency_repo = idempotency_repo

    async def _resolve_user(self, user: User) -> AuthenticatedContext:
        display_name = (user.full_name or user.first_name or "Telegram User").strip()
        actor = ActorScope(
            user_id=UserId.generate(),
            bot_id=self._bot_id,
            command=self._agent_command,
        )
        result = await self._resolve_identity(
            actor,
            Provider.TELEGRAM,
            str(user.id),
            user.username,
            display_name,
        )
        if result.is_failure:
            raise TelegramProcessorError(result.error.message)
        return result.value

    def _actor(self, context: AuthenticatedContext) -> ActorScope:
        return ActorScope(
            user_id=context.internal_user_id,
            bot_id=context.bot_id,
            command=context.command,
        )

    def _event_key(self, provider_event_id: str) -> IdempotencyKey:
        return IdempotencyKey.for_provider_event("telegram", provider_event_id)

    async def _claim_event(self, actor: ActorScope, key: IdempotencyKey) -> OperationId | None:
        operation_id = OperationId.generate()
        existing = await self._idempotency_repo.claim_event(actor, key, operation_id)
        if existing is not None:
            return None
        return operation_id

    async def process_message(self, update: Update, context: Any) -> None:
        """Handle an incoming text or photo message."""

        message = update.message
        if message is None or message.from_user is None or message.chat is None:
            return

        with correlation_id_scope():
            auth_context = await self._resolve_user(message.from_user)
            actor = self._actor(auth_context)
            event_key = self._event_key(str(update.update_id))
            operation_id = await self._claim_event(actor, event_key)
            if operation_id is None:
                METRICS.duplicate_events.labels(kind="provider_event").inc()
                return

            with log_context(
                channel="telegram",
                command=self._agent_command,
                bot_instance=self._bot_id,
                user_id=str(actor.user_id),
                operation_id=str(operation_id),
            ):
                started = time.perf_counter()
                outcome = "success"
                try:
                    logger.info("processing telegram message")
                    attachments = await upload_message_attachments(
                        context.bot, self._register_upload, actor, message
                    )
                    normalized = build_normalized_message(
                        self._bot_id, self._agent_command, update, attachments
                    )
                    response = await self._agent.execute(auth_context, normalized)
                    await send_response(
                        context.bot,
                        int(normalized.conversation_id),
                        response,
                        self._generate_access,
                        actor,
                    )
                    logger.info("telegram message processed")
                except Exception as exc:
                    outcome = "error"
                    logger.exception(
                        "telegram message failed",
                        extra={"error_category": type(exc).__name__},
                    )
                    await self._send_error(context.bot, message.chat.id, exc)
                finally:
                    METRICS.messages.labels(
                        channel="telegram",
                        command=self._agent_command,
                        outcome=outcome,
                    ).inc()
                    METRICS.message_latency.labels(
                        channel="telegram",
                        command=self._agent_command,
                    ).observe(time.perf_counter() - started)
                    with contextlib.suppress(Exception):
                        await self._idempotency_repo.record_operation(
                            actor, event_key, operation_id
                        )

    async def process_callback(self, update: Update, context: Any) -> None:
        """Handle an inline-keyboard approval action."""

        query = update.callback_query
        if (
            query is None
            or query.from_user is None
            or query.message is None
            or query.message.chat is None
        ):
            return

        with correlation_id_scope():
            auth_context = await self._resolve_user(query.from_user)
            actor = self._actor(auth_context)
            event_key = self._event_key(str(update.update_id))
            operation_id = await self._claim_event(actor, event_key)
            if operation_id is None:
                METRICS.duplicate_events.labels(kind="provider_event").inc()
                await query.answer()
                return

            with log_context(
                channel="telegram",
                command=self._agent_command,
                bot_instance=self._bot_id,
                user_id=str(actor.user_id),
                operation_id=str(operation_id),
            ):
                started = time.perf_counter()
                outcome = "success"
                try:
                    logger.info("processing telegram callback")
                    data = query.data
                    if data is None:
                        raise TelegramProcessorError("callback query has no data")

                    parts = data.split(":", maxsplit=1)
                    if len(parts) != 2:
                        raise TelegramProcessorError("invalid callback data")

                    kind, callback_operation_id = parts
                    normalized = build_normalized_callback(
                        self._bot_id, self._agent_command, update, kind, callback_operation_id
                    )
                    response = await self._agent.execute(auth_context, normalized)
                    await send_response(
                        context.bot,
                        int(query.message.chat.id),
                        response,
                        self._generate_access,
                        actor,
                    )
                    await query.answer()
                    logger.info("telegram callback processed")
                except Exception as exc:
                    outcome = "error"
                    logger.exception(
                        "telegram callback failed",
                        extra={"error_category": type(exc).__name__},
                    )
                    await self._send_error(context.bot, query.message.chat.id, exc)
                    with contextlib.suppress(Exception):
                        await query.answer()
                finally:
                    METRICS.messages.labels(
                        channel="telegram",
                        command=self._agent_command,
                        outcome=outcome,
                    ).inc()
                    METRICS.message_latency.labels(
                        channel="telegram",
                        command=self._agent_command,
                    ).observe(time.perf_counter() - started)
                    with contextlib.suppress(Exception):
                        await self._idempotency_repo.record_operation(
                            actor, event_key, operation_id
                        )

    async def _send_error(self, bot: telegram.Bot, chat_id: int | None, exc: Exception) -> None:
        if chat_id is None:
            return
        with contextlib.suppress(Exception):
            await bot.send_message(chat_id=chat_id, text=f"Sorry, I couldn't process that: {exc}")
