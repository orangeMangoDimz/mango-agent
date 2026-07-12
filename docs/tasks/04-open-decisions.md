---
phase: 0
order: "04"
mvp: true
title: Open decisions — confirm starting values
refs:
  - SDD §29 (recommended starting values)
  - SDD §31 (acceptance criteria)
  - PRD §8.4 (priority/status)
---

# 04 — Open decisions — confirm starting values

Goal: Confirm the open product/engineering defaults BEFORE migrations (15) and adapter contracts are finalized. Capture results as ADRs (05).

## Checklist

- [x] Priority values: Low, Medium, High, Urgent.
- [x] Status values: Todo, In progress, Blocked, Done, Cancelled.
- [x] Project title uniqueness: **DEVIATION** — allow duplicate titles per owner (see [00-starting-values](../decisions/00-starting-values.md)).
- [x] Default deletion: soft delete for tasks and projects; retention = indefinite (see [00-starting-values](../decisions/00-starting-values.md)).
- [x] Conversation state expiration: 24h after last activity.
- [x] Proposal expiration: 2h.
- [x] Pending attachment expiration: 24h.
- [x] Presigned URL lifetime: 5 minutes.
- [x] Supported images: JPEG, PNG, WebP.
- [x] Image size limit: 10 MiB.
- [x] Recent context: bounded message window + structured references.
- [x] Sensitive update confirmation scope: ownership, assignee, project move, substantial content replacement.
- [x] Concurrent conversation handling: scoped lock + state version.
- [x] Assignment + group-chat collaboration model: assign to any resolved known internal user; group shared-project opt-in (SDD §19.3, §19.4; see [00-starting-values](../decisions/00-starting-values.md)).
- [x] Project deletion behavior for existing tasks: cascade soft-delete child tasks (SDD §16.2; see [00-starting-values](../decisions/00-starting-values.md)).
- [x] Document confirmed values; flag any deviation from SDD §29 — captured in [docs/decisions/00-starting-values.md](../decisions/00-starting-values.md).
