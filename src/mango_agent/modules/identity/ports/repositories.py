"""Identity repository ports."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.shared.domain.ids import UserId
from mango_agent.shared.ports.actor_scope import ActorScope

__all__ = ["UserRepository", "ProviderIdentityRepository"]


class UserRepository(ABC):
    """Port for persisting and resolving internal users."""

    @abstractmethod
    async def create(self, actor: ActorScope, user: User) -> User:
        """Persist a new user."""

    @abstractmethod
    async def get_by_id(self, actor: ActorScope, user_id: UserId) -> User:
        """Return the user with the given id."""

    @abstractmethod
    async def get_by_provider_identity(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> User:
        """Resolve an internal user by provider identity."""


class ProviderIdentityRepository(ABC):
    """Port for persisting provider identities."""

    @abstractmethod
    async def create(self, actor: ActorScope, identity: ProviderIdentity) -> ProviderIdentity:
        """Persist a new provider identity."""

    @abstractmethod
    async def get_by_natural_key(
        self,
        actor: ActorScope,
        provider: Provider,
        provider_user_id: str,
    ) -> ProviderIdentity:
        """Return the provider identity identified by provider + provider_user_id."""
