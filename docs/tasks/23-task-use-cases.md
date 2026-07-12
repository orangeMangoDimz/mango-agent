---
phase: 4
order: "23"
mvp: true
title: Task use cases (proposal, approved create, CRUD, status)
refs:
  - PRD §7.1-7.5, §9, §14.2
  - SDD §12.3, §14.3, §15, §20.2
  - depends_on: [11, 16, 25]
---

# 23 — Task use cases (proposal, approved create, CRUD, status)

Goal: Task lifecycle use cases with human approval gate, idempotent approved creation, and status transitions.

## Checklist

- [ ] `ValidateTaskProposal`: check required fields, missing-info detection, project match-or-create proposal.
- [ ] `CreateApprovedTask`: independent approval-state verification; model cannot bypass via raw create.
- [ ] Approved creation uses operation ID as idempotency key; op record + task + attachment link in one UoW transaction.
- [ ] `GetTask`, `SearchTasks` (filter by priority/status/project/assignee/time) — reads, no approval.
- [ ] `UpdateTask`: autonomous when safe/unambiguous; sensitive updates (ownership/assignee/project move/substantial content) require confirmation.
- [ ] `TransitionTaskStatus` / complete / reopen: maintain `done_at` invariant.
- [ ] `DeleteTask`: requires explicit confirmation.
- [ ] Update uses updated_at/version conflict check (lost-update protection).
- [ ] Application tests: approved-create transaction, duplicate approval → one task, sensitive-update confirmation, confirmed delete.
