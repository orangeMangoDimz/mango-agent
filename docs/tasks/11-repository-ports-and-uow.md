---
phase: 2
order: "11"
mvp: true
title: Repository ports + Unit of Work
refs:
  - PRD §15.5, §15.7
  - SDD §8 (RepoPorts, UoW), §15
---

# 11 — Repository ports + Unit of Work

Goal: Domain-specific repository interfaces + Unit of Work port in the core; no generic CRUD, no infra types.

## Checklist

- [ ] `UserRepository` / `ProviderIdentityRepository` ports (resolve by provider+id, create with identity mapping).
- [ ] `ProjectRepository` port: create, get (scoped), search, update, delete.
- [ ] `TaskRepository` port: create, get (scoped), search/filter, update, delete, status transition.
- [ ] `AttachmentRepository` port: register pending, link to task, get authorized, list by task, mark lifecycle.
- [ ] `IdempotencyRepository` port: claim provider event, record/lookup business operation.
- [ ] Every read/write method takes actor scope or an authorization spec.
- [ ] `UnitOfWork` port: begin/commit/rollback across multiple repositories atomically.
- [ ] Ports return domain types, not DB rows; expose meaningful operations only.
- [ ] No infra SDK imports in ports.
