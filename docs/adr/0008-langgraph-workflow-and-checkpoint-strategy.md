---
id: ADR-08
title: LangGraph workflow and checkpoint strategy
status: Accepted
date: 2026-07-12
refs:
  - SDD §12
  - SDD §24.5
related:
  - docs/decisions/00-starting-values.md
---

# ADR-08 — LangGraph workflow and checkpoint strategy

## Context

Task management needs explicit state transitions, pause/resume for human approval, and restart-resilient pending workflows. SDD §12.

## Decision

Implement the task-management agent as a **LangGraph workflow** with explicit states (LoadContext → InterpretRequest → create/update/delete/unsupported branches → Respond → SaveContext). Checkpoints are stored in Redis. Proposals and confirmations pause the graph until approval/revision/rejection/confirmation. Step and retry limits are enforced (SDD §12.4).

## Consequences

- Pending approvals survive bot restart (SDD §24.5).
- Tool boundaries map to application use cases; the approved-create use case independently verifies approval state.
- Lost Redis = lost pending workflow state; fail closed (ADR-06).
- Maximum-step termination and bounded retries prevent loops/excess cost; tuned via LangSmith.

## Cross-links

Task-04 confirmed values: proposal **2h** expiration + version invalidation on revision; concurrent conversation handling via **scoped lock + state version**.
ADR-06 (Redis checkpoints), ADR-09 (command registry), task 27 (workflow), task 29 (limits and retry).
