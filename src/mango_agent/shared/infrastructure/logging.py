"""Structured logging with correlation IDs and secret redaction."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from typing import Any

from loguru import logger
from pydantic import SecretStr

from mango_agent.shared.infrastructure.config import LoggingConfig
from mango_agent.shared.infrastructure.correlation import get_correlation_id

_ENV: str = "dev"


@dataclass(frozen=True, slots=True)
class LogContext:
    """Request-scoped dimensions emitted with every structured log line."""

    env: str = "dev"
    bot_instance: str = ""
    channel: str | None = None
    command: str | None = None
    correlation_id: str | None = None
    user_id: str | None = None
    operation_type: str | None = None
    operation_id: str | None = None
    proposal_id: str | None = None
    tool_name: str | None = None
    outcome: str | None = None
    error_category: str | None = None


_LOG_CONTEXT: ContextVar[LogContext | None] = ContextVar(
    "mango_log_context",
    default=None,
)


def get_log_context() -> LogContext:
    return _LOG_CONTEXT.get() or LogContext()


@contextmanager
def log_context(**kwargs: Any) -> Iterator[LogContext]:
    """Set structured-log dimensions for the current async context."""
    previous = get_log_context()
    new = replace(previous, **kwargs)
    token: Token[LogContext | None] = _LOG_CONTEXT.set(new)
    try:
        yield new
    finally:
        _LOG_CONTEXT.reset(token)


def _redact(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return "***"
    if isinstance(value, Mapping):
        return {str(k): _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _json_sink(message: Any) -> None:
    record = message.record
    ctx = get_log_context()
    correlation_id = ctx.correlation_id
    if correlation_id is None:
        current = get_correlation_id()
        if current is not None:
            correlation_id = str(current)

    payload: dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "source": record["name"],
        "env": ctx.env if ctx.env != "dev" else _ENV,
        "bot_instance": ctx.bot_instance,
        "channel": ctx.channel,
        "command": ctx.command,
        "correlation_id": correlation_id,
        "user_id": ctx.user_id,
        "operation_type": ctx.operation_type,
        "operation_id": ctx.operation_id,
        "proposal_id": ctx.proposal_id,
        "tool_name": ctx.tool_name,
        "outcome": ctx.outcome,
        "error_category": ctx.error_category,
    }
    extra = {k: _redact(v) for k, v in record["extra"].items()}
    if extra:
        payload["extra"] = extra

    sys.stderr.write(json.dumps(payload, default=str) + "\n")


def configure_logging(config: LoggingConfig) -> None:
    """Configure Loguru to emit JSON lines with redaction."""
    global _ENV
    _ENV = config.env
    logger.remove()
    logger.add(_json_sink, level=config.log_level.upper())


__all__ = ["LogContext", "configure_logging", "get_log_context", "log_context", "logger"]
