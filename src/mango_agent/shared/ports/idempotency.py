"""Idempotency key value object and repository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import OperationId
from mango_agent.shared.ports.actor_scope import ActorScope

__all__ = ["IdempotencyKey", "IdempotencyRepository"]


@final
@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Composite idempotency key scoped to a source and external identifier."""

    scope: str
    external_id: str

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValidationError("idempotency scope must not be empty")
        if not self.external_id.strip():
            raise ValidationError("idempotency external id must not be empty")

    @classmethod
    def for_provider_event(cls, provider: str, provider_event_id: str) -> IdempotencyKey:
        return cls(
            scope=f"provider_event:{provider.strip()}",
            external_id=provider_event_id.strip(),
        )


class IdempotencyRepository(ABC):
    """Port for claiming and recording idempotent operations."""

    @abstractmethod
    async def claim_event(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        """Claim an event key; return an existing operation id if already processed."""

    @abstractmethod
    async def record_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
        operation_id: OperationId,
    ) -> None:
        """Record the operation id produced for a claimed key."""

    @abstractmethod
    async def lookup_operation(
        self,
        actor: ActorScope,
        key: IdempotencyKey,
    ) -> OperationId | None:
        """Return the recorded operation id for a key, if any."""
