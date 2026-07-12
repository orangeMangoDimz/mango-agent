---
phase: 9
order: "39"
mvp: true
title: Integration & end-to-end tests
refs:
  - PRD §18.2
  - SDD §24.5
  - depends_on: [15, 17, 18, 33]
---

# 39 — Integration & end-to-end tests

Goal: Real-infra integration + a limited Docker end-to-end set.

## Checklist

- [ ] PG migrations from empty DB.
- [ ] Real transaction rollback behavior.
- [ ] Redis conversation isolation across users/bots/threads.
- [ ] Task creation with attachment metadata (PG + R2 + Redis).
- [ ] Docker Compose startup + health checks.
- [ ] Restart during a pending approval (state survives in Redis).
- [ ] Limited E2E: create → approve → search → update → delete via Telegram fixtures.
