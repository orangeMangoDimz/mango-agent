"""Contract tests for PostgreSQL repository adapters."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from mango_agent.modules.identity.adapters.postgres_repositories import (
    PostgresProviderIdentityRepository,
    PostgresUserRepository,
)
from mango_agent.modules.identity.domain.provider import Provider
from mango_agent.modules.identity.domain.provider_identity import ProviderIdentity
from mango_agent.modules.identity.domain.user import User
from mango_agent.modules.task_management.adapters.postgres_repositories import (
    PostgresProjectRepository,
    PostgresTaskRepository,
)
from mango_agent.modules.task_management.domain.project import Project
from mango_agent.modules.task_management.domain.task import Task
from mango_agent.modules.task_management.ports.repositories import ProjectSearchQuery
from mango_agent.shared.domain.value_objects import Pagination
from mango_agent.shared.ports.actor_scope import ActorScope

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    if DSN is None:
        return
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        check=True,
    )


@pytest_asyncio.fixture
async def db_conn() -> asyncpg.Connection:
    if DSN is None:
        pytest.skip("DATABASE_URL not set; start postgres with docker compose up -d postgres")
    conn = await asyncpg.connect(DSN)
    transaction = conn.transaction()
    await transaction.start()
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()


async def test_user_repository_roundtrip(db_conn: asyncpg.Connection) -> None:
    users = PostgresUserRepository(db_conn)
    user = User.create("Dimas")
    actor = ActorScope(user_id=user.id, bot_id="test-bot", command="task_management")
    await users.create(actor, user)
    found = await users.get_by_id(actor, user.id)
    assert found.display_name == "Dimas"


async def test_provider_identity_repository_roundtrip(db_conn: asyncpg.Connection) -> None:
    users = PostgresUserRepository(db_conn)
    identities = PostgresProviderIdentityRepository(db_conn)
    user = User.create("Dimas")
    actor = ActorScope(user_id=user.id, bot_id="test-bot", command="task_management")
    await users.create(actor, user)
    identity = ProviderIdentity.create(user.id, Provider.TELEGRAM, "12345")
    await identities.create(actor, identity)
    found = await identities.get_by_natural_key(actor, Provider.TELEGRAM, "12345")
    assert found.user_id == user.id


async def test_project_repository_roundtrip(db_conn: asyncpg.Connection) -> None:
    users = PostgresUserRepository(db_conn)
    projects = PostgresProjectRepository(db_conn)
    user = User.create("Dimas")
    actor = ActorScope(user_id=user.id, bot_id="test-bot", command="task_management")
    await users.create(actor, user)
    project = Project.create(user.id, "Test Project")
    await projects.create(actor, project)
    found = await projects.get(actor, project.id)
    assert found.title == "Test Project"
    results = await projects.search(actor, ProjectSearchQuery(), Pagination.default())
    assert len(results.items) == 1


async def test_task_repository_roundtrip(db_conn: asyncpg.Connection) -> None:
    users = PostgresUserRepository(db_conn)
    projects = PostgresProjectRepository(db_conn)
    tasks = PostgresTaskRepository(db_conn)
    user = User.create("Dimas")
    actor = ActorScope(user_id=user.id, bot_id="test-bot", command="task_management")
    await users.create(actor, user)
    project = Project.create(user.id, "Test Project")
    await projects.create(actor, project)
    task = Task.create(project.id, "Test Task")
    await tasks.create(actor, task)
    found = await tasks.get(actor, task.id)
    assert found.title == "Test Task"
    transitioned = await tasks.transition_status(actor, task.id, found.status)
    assert transitioned.status == found.status
