---
phase: 10
order: "43"
mvp: true
title: Error handling & recovery
refs:
  - PRD §9, §21 (SDD)
  - SDD §21 (failure table), §22
  - depends_on: [29, 34]
---

# 43 — Error handling & recovery

Goal: Translate infra exceptions to stable app errors; fail closed for approval-dependent flows; clear user-facing behavior per SDD §21.

## Checklist

- [ ] Map: invalid provider event, identity failure, model timeout, invalid tool args, max-steps, PG/Redis unavailable, R2 upload failure, DB failure after R2 upload, provider delivery failure, expired proposal, duplicate approval.
- [ ] Infra exceptions → stable application errors; provider error types never escape to domain/application.
- [ ] No half-finished tasks; do not report mutation success on infra failure.
- [ ] Redis unavailable → block approval-dependent flows; durable data stays safe.
- [ ] R2 upload failure → do not mark pending metadata complete; safe retry with unique op ID.
- [ ] DB failure after upload → mark/detect orphan for cleanup.
- [ ] Expired proposal → refuse approval, offer rebuild from context.
- [ ] Duplicate approval → return original result, no second mutation.
- [ ] Tests covering each failure path.
