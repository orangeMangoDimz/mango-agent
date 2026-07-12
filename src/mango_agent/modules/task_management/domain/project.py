"""Project entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import ProjectId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


@final
@dataclass(frozen=True, slots=True)
class Project:
    id: ProjectId
    owner_user_id: UserId
    title: str
    created_at: Timestamp
    updated_at: Timestamp

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("project title must not be empty")

    @classmethod
    def create(cls, owner_user_id: UserId, title: str) -> Project:
        now = Timestamp.now()
        return cls(
            id=ProjectId.generate(),
            owner_user_id=owner_user_id,
            title=title.strip(),
            created_at=now,
            updated_at=now,
        )

    def rename(self, title: str) -> Project:
        return Project(
            id=self.id,
            owner_user_id=self.owner_user_id,
            title=title.strip(),
            created_at=self.created_at,
            updated_at=Timestamp.now(),
        )
