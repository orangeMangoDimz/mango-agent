"""Application composition root entry point.

Loads and validates configuration at startup (task 03). Concrete adapter
wiring and the Telegram polling loop arrive in tasks 31 and 33.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from mango_agent.shared.infrastructure.config import ConfigError, load_config


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "migrate" in args:
        print("migrate: not implemented yet (see task 15)")
        return 0

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"mango-agent: {exc}", file=sys.stderr)
        return 1

    print(
        "mango-app starting: "
        f"instance={config.instance.bot_instance} "
        f"channel={config.channel.channel} "
        f"agent_command={config.instance.agent_command} "
        f"env={config.logging.env}"
    )
    print("(no polling loop yet - task 31)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
