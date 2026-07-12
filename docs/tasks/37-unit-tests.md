---
phase: 9
order: "37"
mvp: true
title: Unit tests (domain, application, agent)
refs:
  - PRD §18.2
  - SDD §24.1, §24.2, §24.3
  - depends_on: [36]
---

# 37 — Unit tests (domain, application, agent)

Goal: No-infra unit tests for domain rules, use cases, and agent workflow using fakes.

## Checklist

- [ ] Domain: status/done_at invariants, priority/status validation, project ownership, attachment lifecycle, proposal version invariants.
- [ ] Application: authorized project/task CRUD, cross-user rejection, approved-create transaction, duplicate approval → one task, sensitive-update confirmation, confirmed delete, attachment link + cleanup compensation.
- [ ] Agent: missing-info follow-up, proposal generation, approve/revise/reject/expire, ambiguous update targeting, delete confirmation, invalid-arg repair, max-step termination, deterministic model responses.
- [ ] All via injected fakes; no real infra.
- [ ] Fast suite in CI.
