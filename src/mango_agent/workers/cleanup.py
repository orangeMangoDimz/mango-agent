"""Composition root for the attachment cleanup worker."""

from __future__ import annotations

from mango_agent.modules.attachments.adapters.r2_storage import (
    R2AttachmentStorage,
    R2StorageConfig,
)
from mango_agent.modules.attachments.application.cleanup import (
    CleanUpAttachments,
    CleanupSummary,
)
from mango_agent.shared.adapters.postgres.unit_of_work import PostgresUnitOfWork
from mango_agent.shared.infrastructure.config import WorkerConfig, load_worker_config
from mango_agent.shared.infrastructure.logging import log_context, logger
from mango_agent.shared.infrastructure.postgres.connection import PostgresConnectionPool


def _build_r2_storage(config: WorkerConfig) -> R2AttachmentStorage:
    r2 = config.r2
    if (
        r2.r2_account_id is None
        or r2.r2_access_key_id is None
        or r2.r2_secret_access_key is None
        or r2.r2_bucket is None
    ):
        raise RuntimeError("R2 configuration is required for attachment cleanup")
    return R2AttachmentStorage(
        R2StorageConfig(
            account_id=r2.r2_account_id,
            access_key_id=r2.r2_access_key_id.get_secret_value(),
            secret_access_key=r2.r2_secret_access_key.get_secret_value(),
            bucket=r2.r2_bucket,
        )
    )


async def run_cleanup(config: WorkerConfig | None = None) -> CleanupSummary:
    """Run one attachment cleanup pass and return the summary."""
    if config is None:
        config = load_worker_config()

    with log_context(
        bot_instance=config.instance.bot_instance,
        command="cleanup",
        operation_type="attachment_cleanup",
    ):
        logger.info("cleanup started")
        pool = PostgresConnectionPool(config.postgres.database_url.get_secret_value())
        await pool.connect()
        try:
            storage = _build_r2_storage(config)
            use_case = CleanUpAttachments(
                uow_factory=lambda: PostgresUnitOfWork(pool),
                storage=storage,
            )
            result = await use_case()
            if result.is_failure:
                raise RuntimeError(f"cleanup failed: {result.error.message}")
            summary = result.value
            logger.info("cleanup completed", extra={"summary": summary})
            return summary
        finally:
            await pool.disconnect()
