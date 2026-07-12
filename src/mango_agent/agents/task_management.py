"""Task management agent stub."""

from __future__ import annotations

import time
from typing import final

from mango_agent.agents.contract import Agent, NormalizedRequest
from mango_agent.modules.identity.application.use_cases import AuthenticatedContext
from mango_agent.shared.channel_contracts import NormalizedOutboundResponse
from mango_agent.shared.infrastructure.logging import log_context, logger
from mango_agent.shared.infrastructure.metrics import METRICS

__all__ = ["TaskManagementAgent"]


@final
class TaskManagementAgent(Agent):
    """Agent that handles task-management conversations."""

    def __init__(self, use_cases: dict[str, object]) -> None:
        self._use_cases = use_cases

    async def execute(
        self,
        context: AuthenticatedContext,
        payload: NormalizedRequest,
    ) -> NormalizedOutboundResponse:
        with log_context(
            command=payload.agent_command,
            user_id=str(context.internal_user_id),
        ):
            started = time.perf_counter()
            outcome = "success"
            try:
                logger.info("agent executing")
                response = NormalizedOutboundResponse.final_text(
                    f"Task management agent received: {payload.message_text}",
                )
                logger.info("agent completed")
                return response
            except Exception as exc:
                outcome = "error"
                logger.exception("agent failed", extra={"error_category": type(exc).__name__})
                raise
            finally:
                METRICS.agent_executions.labels(
                    command=payload.agent_command, outcome=outcome
                ).inc()
                METRICS.agent_execution_latency.labels(command=payload.agent_command).observe(
                    time.perf_counter() - started
                )
