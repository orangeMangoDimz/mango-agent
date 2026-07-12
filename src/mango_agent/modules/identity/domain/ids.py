"""Typed IDs for the identity domain."""

from __future__ import annotations

from typing import final

from mango_agent.shared.domain.ids import EntityId


@final
class ProviderIdentityId(EntityId):
    """Identifies a provider identity."""
