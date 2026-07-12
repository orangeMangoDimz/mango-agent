---
phase: 9
order: "36"
mvp: true
title: Test fakes & harness (in-memory repos, fake model)
refs:
  - PRD §18.2
  - SDD §24
  - depends_on: [11, 12, 13, 14]
---

# 36 — Test fakes & harness (in-memory repos, fake model)

Goal: `tests/fakes/` providing in-memory ports + deterministic fake model so unit/agent tests run without infra.

## Checklist

- [ ] In-memory repository fakes (User/Project/Task/Attachment/Idempotency).
- [ ] In-memory UoW fake (commit/rollback semantics).
- [ ] In-memory conversation/proposal/confirmation state fake with expiration emulation.
- [ ] In-memory attachment storage fake (key gen, presign, delete).
- [ ] Deterministic fake model with scriptable tool-call responses.
- [ ] Fake tracing (no-op) + provider event fixtures.
- [ ] Shared test harness builder to wire fakes quickly.
