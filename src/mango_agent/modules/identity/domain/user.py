"""Internal user entity."""

from __future__ import annotations

from dataclasses import dataclass

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp


@dataclass(slots=True)
class User:
    """A person interacting with Mango Agent.

    Provider metadata is never inferred from model output; identities are
    created from trusted provider events in the application layer.
    """

    id: UserId
    display_name: str
    created_at: Timestamp
    updated_at: Timestamp

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("display name must not be empty")

    @classmethod
    def create(cls, display_name: str) -> User:
        now = Timestamp.now()
        return cls(
            id=UserId.generate(),
            display_name=display_name.strip(),
            created_at=now,
            updated_at=now,
        )

    def update_display_name(self, display_name: str) -> None:
        stripped = display_name.strip()
        if not stripped:
            raise ValidationError("display name must not be empty")
        self.display_name = stripped
        self.updated_at = Timestamp.now()
