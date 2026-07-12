from __future__ import annotations

from mango_agent.modules.identity.domain.provider import Provider


def test_provider_values() -> None:
    assert Provider.TELEGRAM == "telegram"
    assert Provider.DISCORD == "discord"
