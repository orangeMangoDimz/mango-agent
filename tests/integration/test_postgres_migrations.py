"""Integration test for Postgres migrations via Alembic."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DATABASE_URL not set; start postgres with docker compose up -d postgres",
)
def test_alembic_migrations_apply_and_rollback() -> None:
    env = os.environ.copy()
    upgrade = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert upgrade.returncode == 0

    downgrade = subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert downgrade.returncode == 0
