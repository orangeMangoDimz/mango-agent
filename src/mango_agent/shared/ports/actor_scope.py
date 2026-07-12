"""Actor scope for authorization in ports and use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId


@final
@dataclass(frozen=True, slots=True)
class ActorScope:
    user_id: UserId
    bot_id: str
    command: str | None = None

    def __post_init__(self) -> None:
        if not self.bot_id.strip():
            raise ValidationError("bot id must not be empty")
