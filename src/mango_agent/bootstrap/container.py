"""Dependency-injector composition root for Mango Agent.

The container wires infrastructure adapters and application use cases. The
loaded :class:`AppConfig` is injected as a single object provider so secrets
are resolved once and downstream providers can extract typed values with
simple callables.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, final

import redis.asyncio as redis
from dependency_injector import containers, providers

from mango_agent.integrations.llm.anthropic_model import AnthropicModelPort
from mango_agent.integrations.llm.langsmith_tracing import LangSmithTracingPort
from mango_agent.modules.attachments.adapters.r2_storage import (
    R2AttachmentStorage,
    R2StorageConfig,
)
from mango_agent.modules.attachments.application.use_cases import (
    GenerateAccess,
    LinkAttachmentToTask,
    RegisterPendingUpload,
    RejectOrExpireAttachment,
)
from mango_agent.modules.attachments.ports import AttachmentStorage
from mango_agent.modules.conversation.adapters.redis_state_store import (
    RedisConfirmationStore,
    RedisConversationStateStore,
    RedisProposalStore,
)
from mango_agent.modules.conversation.application.use_cases import (
    ClearCompletedOrRejectedState,
    ConsumeConfirmation,
    ConsumeProposalApproval,
    CreatePendingConfirmation,
    CreatePendingProposal,
    LoadScopedState,
    ReviseProposal,
    SaveScopedState,
)
from mango_agent.modules.identity.application.use_cases import (
    GetUser,
    ResolveProviderIdentity,
    SearchKnownUsers,
)
from mango_agent.modules.task_management.application.projects import (
    CreateProject,
    DeleteConfirmedProject,
    DeleteProject,
    GetProject,
    SearchProjects,
    UpdateProject,
)
from mango_agent.modules.task_management.application.tasks import (
    CreateApprovedTask,
    DeleteTask,
    GetTask,
    SearchTasks,
    TransitionTaskStatus,
    UpdateTask,
    ValidateTaskProposal,
)
from mango_agent.shared.adapters.postgres.idempotency import PostgresIdempotencyRepository
from mango_agent.shared.adapters.postgres.unit_of_work import PostgresUnitOfWork
from mango_agent.shared.infrastructure.config import AppConfig
from mango_agent.shared.infrastructure.postgres.connection import PostgresConnectionPool
from mango_agent.shared.ports.idempotency import IdempotencyRepository
from mango_agent.shared.ports.model import ModelPort
from mango_agent.shared.ports.tracing import TracingPort


async def _postgres_pool(dsn: str) -> AsyncGenerator[PostgresConnectionPool]:
    pool = PostgresConnectionPool(dsn)
    await pool.connect()
    try:
        yield pool
    finally:
        await pool.disconnect()


async def _redis_client(url: str) -> AsyncGenerator[redis.Redis]:
    client = redis.from_url(url, decode_responses=False)
    try:
        yield client
    finally:
        await client.close()


async def _idempotency_repository(
    pool: PostgresConnectionPool,
) -> AsyncGenerator[IdempotencyRepository]:
    """Provide a long-lived idempotency repository for provider event claims."""
    connection = await pool.acquire()
    try:
        yield PostgresIdempotencyRepository(connection)
    finally:
        pool.release(connection)


def _r2_storage_config(config: AppConfig) -> R2StorageConfig:
    r2 = config.r2
    if (
        r2.r2_account_id is None
        or r2.r2_access_key_id is None
        or r2.r2_secret_access_key is None
        or r2.r2_bucket is None
    ):
        raise RuntimeError("R2 configuration is required for attachment storage")
    return R2StorageConfig(
        account_id=r2.r2_account_id,
        access_key_id=r2.r2_access_key_id.get_secret_value(),
        secret_access_key=r2.r2_secret_access_key.get_secret_value(),
        bucket=r2.r2_bucket,
    )


def _attachment_storage(config: AppConfig) -> AttachmentStorage:
    return R2AttachmentStorage(_r2_storage_config(config))


def _model_port(config: AppConfig) -> ModelPort:
    return AnthropicModelPort(
        model=config.model.anthropic_model,
        api_key=config.model.anthropic_api_key,
    )


def _tracing_port(config: AppConfig) -> TracingPort:
    return LangSmithTracingPort(
        api_key=config.langsmith.langsmith_api_key,
        project_name=config.langsmith.langsmith_project,
        enabled=config.langsmith.langsmith_enabled,
    )


def _unit_of_work_factory(pool: PostgresConnectionPool) -> Any:
    """Return a factory that creates a new PostgresUnitOfWork per transaction."""
    return lambda: PostgresUnitOfWork(pool)


@final
class MangoContainer(containers.DeclarativeContainer):
    """Wires all adapters and use cases for a single Mango bot instance."""

    # Loaded application configuration; overridden by the bootstrap entry point.
    app_config = providers.Object(AppConfig)

    # Value extractors from the typed configuration.
    postgres_dsn = providers.Callable(
        lambda cfg: cfg.postgres.database_url.get_secret_value(),
        app_config,
    )
    redis_url = providers.Callable(
        lambda cfg: cfg.redis.redis_url.get_secret_value(),
        app_config,
    )

    # Infrastructure resources with async lifecycle management.
    postgres_pool = providers.Resource(
        _postgres_pool,
        dsn=postgres_dsn,
    )
    redis_client = providers.Resource(
        _redis_client,
        url=redis_url,
    )
    attachment_storage = providers.Singleton(
        _attachment_storage,
        config=app_config,
    )
    model_port = providers.Singleton(_model_port, config=app_config)
    tracing_port = providers.Singleton(_tracing_port, config=app_config)

    # Unit of work factory: a new transaction boundary per use-case invocation.
    unit_of_work = providers.Singleton(
        _unit_of_work_factory,
        pool=postgres_pool,
    )

    # Long-lived idempotency repository for provider event claims.
    idempotency_repository = providers.Resource(
        _idempotency_repository,
        pool=postgres_pool,
    )

    # Conversation state stores backed by Redis.
    state_store = providers.Singleton(
        RedisConversationStateStore,
        redis=redis_client,
    )
    proposal_store = providers.Singleton(
        RedisProposalStore,
        redis=redis_client,
    )
    confirmation_store = providers.Singleton(
        RedisConfirmationStore,
        redis=redis_client,
    )

    # Identity use cases.
    resolve_identity = providers.Factory(
        ResolveProviderIdentity,
        uow_factory=unit_of_work,
    )
    get_user = providers.Factory(
        GetUser,
        uow_factory=unit_of_work,
    )
    search_known_users = providers.Factory(
        SearchKnownUsers,
        uow_factory=unit_of_work,
    )

    # Project use cases.
    create_project = providers.Factory(
        CreateProject,
        uow_factory=unit_of_work,
    )
    get_project = providers.Factory(
        GetProject,
        uow_factory=unit_of_work,
    )
    search_projects = providers.Factory(
        SearchProjects,
        uow_factory=unit_of_work,
    )
    update_project = providers.Factory(
        UpdateProject,
        uow_factory=unit_of_work,
    )
    delete_project = providers.Factory(
        DeleteProject,
        uow_factory=unit_of_work,
    )
    delete_confirmed_project = providers.Factory(
        DeleteConfirmedProject,
        delete_project=delete_project,
        confirmation_store=confirmation_store,
    )

    # Task use cases.
    validate_task_proposal = providers.Factory(ValidateTaskProposal)
    create_approved_task = providers.Factory(
        CreateApprovedTask,
        proposal_store=proposal_store,
        uow_factory=unit_of_work,
    )
    get_task = providers.Factory(
        GetTask,
        uow_factory=unit_of_work,
    )
    search_tasks = providers.Factory(
        SearchTasks,
        uow_factory=unit_of_work,
    )
    update_task = providers.Factory(
        UpdateTask,
        uow_factory=unit_of_work,
        confirmation_store=confirmation_store,
    )
    transition_task_status = providers.Factory(
        TransitionTaskStatus,
        uow_factory=unit_of_work,
    )
    delete_task = providers.Factory(
        DeleteTask,
        uow_factory=unit_of_work,
        confirmation_store=confirmation_store,
    )

    # Attachment use cases.
    register_pending_upload = providers.Factory(
        RegisterPendingUpload,
        uow_factory=unit_of_work,
        storage=attachment_storage,
    )
    generate_access = providers.Factory(
        GenerateAccess,
        uow_factory=unit_of_work,
        storage=attachment_storage,
    )
    link_attachment_to_task = providers.Factory(
        LinkAttachmentToTask,
        uow_factory=unit_of_work,
    )
    reject_or_expire_attachment = providers.Factory(
        RejectOrExpireAttachment,
        uow_factory=unit_of_work,
        storage=attachment_storage,
    )

    # Conversation use cases.
    load_scoped_state = providers.Factory(
        LoadScopedState,
        store=state_store,
    )
    save_scoped_state = providers.Factory(
        SaveScopedState,
        store=state_store,
    )
    create_pending_proposal = providers.Factory(
        CreatePendingProposal,
        store=proposal_store,
    )
    revise_proposal = providers.Factory(
        ReviseProposal,
        store=proposal_store,
    )
    consume_proposal_approval = providers.Factory(
        ConsumeProposalApproval,
        store=proposal_store,
    )
    create_pending_confirmation = providers.Factory(
        CreatePendingConfirmation,
        store=confirmation_store,
    )
    consume_confirmation = providers.Factory(
        ConsumeConfirmation,
        store=confirmation_store,
    )
    clear_completed_or_rejected_state = providers.Factory(
        ClearCompletedOrRejectedState,
        state_store=state_store,
        proposal_store=proposal_store,
        confirmation_store=confirmation_store,
    )
