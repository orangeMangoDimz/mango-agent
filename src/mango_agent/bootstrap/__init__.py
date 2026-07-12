"""Application composition root entry point.

Loads and validates configuration at startup, wires concrete adapters through
``dependency-injector``, verifies connectivity, and runs the configured channel
bot with graceful shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from collections.abc import Sequence
from typing import Any

import discord
from dependency_injector import providers

from mango_agent.agents.registry import AgentRegistry
from mango_agent.agents.task_management import TaskManagementAgent
from mango_agent.channels.discord._processor import DiscordMessageProcessor
from mango_agent.channels.discord.bot import DiscordGateway
from mango_agent.channels.telegram._processor import TelegramMessageProcessor
from mango_agent.channels.telegram.bot import TelegramBot
from mango_agent.shared.infrastructure.config import AppConfig, ConfigError, load_config
from mango_agent.shared.infrastructure.logging import configure_logging

from .container import MangoContainer


class StartupError(Exception):
    """Raised when startup validation fails."""


def _build_use_cases(container: MangoContainer) -> dict[str, Any]:
    """Collect all application use cases for the task-management agent."""
    return {
        "resolve_identity": container.resolve_identity(),
        "get_user": container.get_user(),
        "search_known_users": container.search_known_users(),
        "create_project": container.create_project(),
        "get_project": container.get_project(),
        "search_projects": container.search_projects(),
        "update_project": container.update_project(),
        "delete_confirmed_project": container.delete_confirmed_project(),
        "validate_task_proposal": container.validate_task_proposal(),
        "create_approved_task": container.create_approved_task(),
        "get_task": container.get_task(),
        "search_tasks": container.search_tasks(),
        "update_task": container.update_task(),
        "transition_task_status": container.transition_task_status(),
        "delete_task": container.delete_task(),
        "register_pending_upload": container.register_pending_upload(),
        "generate_access": container.generate_access(),
        "link_attachment_to_task": container.link_attachment_to_task(),
        "reject_or_expire_attachment": container.reject_or_expire_attachment(),
        "load_scoped_state": container.load_scoped_state(),
        "save_scoped_state": container.save_scoped_state(),
        "create_pending_proposal": container.create_pending_proposal(),
        "revise_proposal": container.revise_proposal(),
        "consume_proposal_approval": container.consume_proposal_approval(),
        "create_pending_confirmation": container.create_pending_confirmation(),
        "consume_confirmation": container.consume_confirmation(),
        "clear_completed_or_rejected_state": container.clear_completed_or_rejected_state(),
    }


def _build_agent_registry(container: MangoContainer) -> AgentRegistry:
    """Register the configured agent command with the task-management agent."""
    registry = AgentRegistry()
    use_cases = _build_use_cases(container)
    registry.register(
        "task_management",
        lambda _deps: TaskManagementAgent(use_cases),
    )
    return registry


def _build_telegram_bot(config: AppConfig, container: MangoContainer) -> TelegramBot:
    """Build a Telegram polling bot wired to the configured task agent."""
    registry = _build_agent_registry(container)
    telegram_token = config.channel.telegram_bot_token
    assert telegram_token is not None, "TELEGRAM_BOT_TOKEN is required for telegram channel"
    token = telegram_token.get_secret_value()
    processor = TelegramMessageProcessor(
        bot_id=config.instance.bot_instance,
        agent_command=config.instance.agent_command,
        agent=registry.build(config.instance.agent_command, None),
        resolve_identity=container.resolve_identity(),
        register_upload=container.register_pending_upload(),
        generate_access=container.generate_access(),
        idempotency_repo=container.idempotency_repository(),
    )
    return TelegramBot(token, processor)


class _DiscordBot:
    """Small wrapper giving the Discord gateway a uniform start/stop surface."""

    def __init__(self, gateway: DiscordGateway, token: str) -> None:
        self._gateway = gateway
        self._token = token

    async def start(self) -> None:
        await self._gateway.start(self._token)

    async def stop(self) -> None:
        await self._gateway.close()


def _build_discord_gateway(config: AppConfig, container: MangoContainer) -> _DiscordBot:
    """Build a Discord gateway bot wired to the configured task agent."""
    registry = _build_agent_registry(container)
    intents = discord.Intents.default()
    intents.message_content = True
    processor = DiscordMessageProcessor(
        bot_id=config.instance.bot_instance,
        agent_command=config.instance.agent_command,
        agent=registry.build(config.instance.agent_command, None),
        resolve_identity=container.resolve_identity(),
        idempotency_repo=container.idempotency_repository(),
    )
    gateway = DiscordGateway(processor, intents=intents)
    discord_token = config.channel.discord_token
    assert discord_token is not None, "DISCORD_TOKEN is required for discord channel"
    return _DiscordBot(gateway, discord_token.get_secret_value())


async def _verify_connectivity(container: MangoContainer) -> None:
    """Fail fast if required dependencies are not reachable."""
    try:
        pool = container.postgres_pool()
        connection = await pool.acquire()
        try:
            await connection.fetch("SELECT 1")
        finally:
            pool.release(connection)
    except Exception as exc:
        raise StartupError(f"PostgreSQL connectivity check failed: {exc}") from exc

    try:
        redis_client = container.redis_client()
        if not await redis_client.ping():
            raise StartupError("Redis ping returned falsy response")
    except Exception as exc:
        raise StartupError(f"Redis connectivity check failed: {exc}") from exc

    # Model instantiation validates the configuration; we do not invoke it
    # during startup to avoid consuming tokens before polling begins.
    container.model_port()


def _build_bot(config: AppConfig, container: MangoContainer) -> TelegramBot | _DiscordBot:
    """Create the configured channel bot without starting it."""
    if config.channel.channel == "telegram":
        return _build_telegram_bot(config, container)
    if config.channel.channel == "discord":
        return _build_discord_gateway(config, container)
    raise StartupError(f"unsupported channel: {config.channel.channel}")


async def _init_resources(container: MangoContainer) -> None:
    """Initialize async resources, handling sync or async container APIs."""
    init = container.init_resources()
    if init is not None:
        await init


async def _shutdown_resources(container: MangoContainer) -> None:
    """Shutdown async resources, handling sync or async container APIs."""
    shutdown = container.shutdown_resources()
    if shutdown is not None:
        await shutdown


async def _shutdown(container: MangoContainer) -> None:
    """Flush traces and close managed resources."""
    await _shutdown_resources(container)


async def _async_main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "migrate" in args:
        print("migrate: run via the dedicated migrations service (task 15)")
        return 0

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"mango-agent: {exc}", file=sys.stderr)
        return 1

    configure_logging(config.logging)

    container = MangoContainer()
    container.app_config.override(providers.Object(config))

    try:
        await _init_resources(container)
    except Exception as exc:
        print(f"mango-agent: resource initialization failed: {exc}", file=sys.stderr)
        return 1

    try:
        await _verify_connectivity(container)
    except StartupError as exc:
        print(f"mango-agent: {exc}", file=sys.stderr)
        await _shutdown(container)
        return 1

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    bot = _build_bot(config, container)
    bot_task = asyncio.create_task(bot.start())
    try:
        await shutdown_event.wait()
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)

        await bot.stop()
        with contextlib.suppress(Exception):
            bot_task.cancel()
            await bot_task

        await _shutdown(container)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous entry point for the console script."""
    try:
        return asyncio.run(_async_main(argv))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
