---
phase: 3
order: "16"
mvp: true
title: PostgreSQL repository adapters
refs:
  - PRD §15.5, §18
  - SDD §8 (PgAdapter), §19.2
  - depends_on: [11, 15]
---

# 16 — PostgreSQL repository adapters

Goal: Implement repository + UoW ports over Postgres with user-scoped queries and domain mapping.

## Checklist

- [ ] Implement User/ProviderIdentity repositories (find-or-create mapping).
- [ ] Implement Project repository (scoped CRUD, search).
- [ ] Implement Task repository (scoped CRUD, search/filter, status transition + done_at).
- [ ] Implement Attachment repository (pending, link, authorized get, lifecycle).
- [ ] Implement Idempotency repository (claim event, record/lookup operation).
- [ ] Implement Unit of Work (begin/commit/rollback) across repositories.
- [ ] All reads/writes enforce actor scope; no unscoped by-ID access as authorization.
- [ ] Domain↔persistence mapping isolated; infra errors translated to app errors.
- [ ] Update path uses updated_at/version check for lost-update protection.
- [ ] Contract tests against a real Postgres.
