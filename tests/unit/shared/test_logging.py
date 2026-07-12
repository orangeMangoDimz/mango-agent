"""Unit tests for structured logging context."""

from __future__ import annotations

from mango_agent.shared.infrastructure.logging import LogContext, get_log_context, log_context


def test_default_log_context() -> None:
    assert get_log_context() == LogContext()


def test_log_context_overrides() -> None:
    with log_context(channel="telegram", command="test"):
        ctx = get_log_context()
        assert ctx.channel == "telegram"
        assert ctx.command == "test"
        assert ctx.env == "dev"


def test_nested_log_context_restores_previous() -> None:
    with log_context(channel="telegram"):
        with log_context(command="inner"):
            ctx = get_log_context()
            assert ctx.channel == "telegram"
            assert ctx.command == "inner"
        ctx = get_log_context()
        assert ctx.command is None
