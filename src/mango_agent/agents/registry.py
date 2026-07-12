"""Command-based agent registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import final

from mango_agent.agents.contract import Agent, AgentCommandError

type AgentFactory = Callable[..., Agent]

__all__ = ["AgentFactory", "AgentRegistry"]


@final
class AgentRegistry:
    """Deterministic command registry mapping commands to agent factories."""

    def __init__(self) -> None:
        self._factories: dict[str, AgentFactory] = {}

    def register(self, command: str, factory: AgentFactory) -> None:
        """Register a factory for the given command."""
        if not command.strip():
            raise AgentCommandError("command must not be empty")
        self._factories[command] = factory

    def resolve(self, command: str) -> AgentFactory:
        """Return the factory registered for the given command."""
        factory = self._factories.get(command)
        if factory is None:
            available = ", ".join(sorted(self._factories)) or "none"
            raise AgentCommandError(
                f"unknown command: {command!r}. Available commands: {available}"
            )
        return factory

    def build(self, command: str, dependencies: object) -> Agent:
        """Resolve the command and build an agent instance using the provided dependencies."""
        factory = self.resolve(command)
        return factory(dependencies)
