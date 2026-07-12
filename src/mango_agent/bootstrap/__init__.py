"""Application composition root entry point.

Minimal fail-fast stub for task 02 (Docker Compose local dev). The full typed
configuration object and concrete adapter wiring arrive in tasks 03
(configuration) and 33 (composition root).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

REQUIRED_VARS = ("CHANNEL", "BOT_INSTANCE", "AGENT_COMMAND", "DATABASE_URL", "REDIS_URL")


def _resolved_config() -> dict[str, str]:
    return {name: os.environ.get(name, "") for name in REQUIRED_VARS}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "migrate" in args:
        print("migrate: not implemented yet (see task 15)")
        return 0

    config = _resolved_config()
    missing = [name for name, value in config.items() if not value]
    if missing:
        print(
            "mango-agent: refusing to start - missing required env: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    print(
        "mango-app starting: "
        f"instance={config['BOT_INSTANCE']} "
        f"channel={config['CHANNEL']} "
        f"agent_command={config['AGENT_COMMAND']}"
    )
    print("(no polling loop yet - task 31)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
