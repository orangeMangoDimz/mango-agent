"""Dependency-rule guard.

Runs ``lint-imports`` against the contracts in ``pyproject.toml`` and fails
the suite if any hexagonal-layering or infrastructure-isolation contract is
broken. This keeps the Channels → Agents → Application → Domain/Ports ←
Adapters invariant enforceable from the first commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_hexagonal_and_infrastructure_contracts_hold() -> None:
    result = subprocess.run(
        ["lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "import-linter contracts broken.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
