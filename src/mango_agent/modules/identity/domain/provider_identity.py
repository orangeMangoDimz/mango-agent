"""Provider identity entity."""

from __future__ import annotations

from dataclasses import dataclass

from mango_agent.modules.identity.domain.ids import ProviderIdentityId
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.domain.value_objects import Timestamp


@dataclass(slots=True, eq=False)
class ProviderIdentity:
    """A provider-specific identity linked to exactly one internal user.

    Equality is based on the natural key (provider, provider_user_id), which
    must be unique across the system. The repository enforces that this key
    maps to a single internal user.
    """

    id: ProviderIdentityId
    user_id: UserId
    provider: Provider
    provider_user_id: str
    username: str | None
    created_at: Timestamp
    updated_at: Timestamp

    def __post_init__(self) -> None:
        if not self.provider_user_id.strip():
            raise ValidationError("provider user id must not be empty")
        if not isinstance(self.provider, Provider):
            raise ValidationError("provider must be a Provider value")

    @classmethod
    def create(
        cls,
        user_id: UserId,
        provider: Provider,
        provider_user_id: str,
        username: str | None = None,
    ) -> ProviderIdentity:
        now = Timestamp.now()
        return cls(
            id=ProviderIdentityId.generate(),
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id.strip(),
            username=username,
            created_at=now,
            updated_at=now,
        )

    def update_username(self, username: str | None) -> None:
        self.username = username
        self.updated_at = Timestamp.now()

    def natural_key(self) -> tuple[Provider, str]:
        return (self.provider, self.provider_user_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProviderIdentity):
            return NotImplemented
        return self.natural_key() == other.natural_key()

    def __hash__(self) -> int:
        return hash(self.natural_key())
