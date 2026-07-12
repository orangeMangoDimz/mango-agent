---
id: ADR-10
title: Unit of Work and idempotent mutation strategy
status: Accepted
date: 2026-07-12
refs:
  - SDD §15
  - SDD §20
related:
  - docs/decisions/00-starting-values.md
---

# ADR-10 — Unit of Work and idempotent mutation strategy

## Context

Related repositories must commit atomically, and duplicate provider events or duplicate approvals must never create duplicate business records. SDD §15 and §20.

## Decision

A **Unit of Work** coordinates PostgreSQL repositories in one transaction. Two distinct idempotency layers: (1) **provider-event idempotency** via a durable claim keyed by provider-scoped event ID; (2) **business-operation idempotency** via a stable operation ID + version, recorded in the same transaction as the mutation. R2 cannot join a PG transaction, so attachment workflows use a compensating lifecycle (ADR-11). Task updates use an updated-at/version check and return a conflict rather than silently overwriting.

## Consequences

- Approved task creation, attachment linking, and idempotency completion commit atomically; a repeated approval returns the previously created task.
- R2 upload failures are compensated by cleanup (ADR-11).
- Concurrent edits produce a conflict response, not lost updates.

## Cross-links

Task-04 confirmed values: **project deletion cascades soft-delete** to child tasks within one UoW transaction.
ADR-05 (PostgreSQL), ADR-11 (attachment compensation), task 11 (repository ports + UoW), task 34 (idempotency).
