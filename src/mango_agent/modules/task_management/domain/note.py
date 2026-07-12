"""Task note value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId


@final
@dataclass(frozen=True, slots=True)
class Note:
    user_text: str
    image_attachment_id: AttachmentId | None = None
    filename: str | None = None
    description: str | None = None
    r2_object_key: str | None = None

    def __post_init__(self) -> None:
        if not self.user_text.strip() and self.image_attachment_id is None:
            raise ValidationError("note must contain text or an image attachment")
