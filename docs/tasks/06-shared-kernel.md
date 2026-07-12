---
phase: 1
order: "06"
mvp: true
title: Shared kernel (IDs, errors, value objects)
refs:
  - PRD §15, §20 (shared/)
  - SDD §4.2 (dependency inversion)
---

# 06 — Shared kernel (IDs, errors, value objects)

Goal: Reusable primitives in `shared/domain` and `shared/infrastructure` with NO infra imports. Not a dumping ground for domain logic.

## Checklist

- [ ] Typed ID value object (UUID-based) for User, Project, Task, Attachment, Operation.
- [ ] Base domain error/exception hierarchy (application-level, no infra types leak).
- [ ] Common value objects: timestamps, pagination, ordered result envelope.
- [ ] Correlation ID carrier for request-scoped propagation.
- [ ] Immutable result/error types used across use cases.
- [ ] No imports of Postgres/Redis/R2/Anthropic/Telegram/Discord in `shared/`.
- [ ] Unit tests for ID equality, error mapping, immutability.
