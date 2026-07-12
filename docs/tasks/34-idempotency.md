---
phase: 8
order: "34"
mvp: true
title: Idempotency — provider events & business operations
refs:
  - PRD §8.5 (idempotency), §13.1
  - SDD §11, §20, §13.1
  - AGENTS.md (idempotency invariant)
  - depends_on: [16, 23, 25]
---

# 34 — Idempotency — provider events & business operations

Goal: No duplicate records from repeated provider events or repeated approvals/retries.

## Checklist

- [ ] Provider-event idempotency: claim by provider-scoped unique event id; duplicate returns prior result / no-op.
- [ ] Durable claim (not just cache) for mutating operations; failed claims retriable via status transition.
- [ ] Business-operation idempotency: each proposal gets stable operation ID + version.
- [ ] Approved task creation uses operation ID as idempotency key; op record + task + link in one transaction.
- [ ] Repeated approval returns the previously created task (no second mutation).
- [ ] Mark provider event completed after processing.
- [ ] Tests: duplicate event, duplicate approval, retry after transient failure.
