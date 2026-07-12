---
phase: 1
order: "08"
mvp: true
title: Task management domain (Project, Task, enums, invariants)
refs:
  - PRD §8.2, §8.3, §8.4
  - SDD §16.2, §16.3
  - SDD §29 (priority/status values)
---

# 08 — Task management domain (Project, Task, enums, invariants)

Goal: Pure domain model for Project and Task with enforced lifecycle invariants; no infra.

## Checklist

- [ ] `Project` entity: id, owner_user_id, title, created/updated at.
- [ ] `Task` entity: id, project_id, title, description, priority, status, tags, assigned_by/assigned_to, note, created/updated/done_at.
- [ ] `Priority` enum: Low, Medium, High, Urgent.
- [ ] `Status` enum: Todo, In progress, Blocked, Done, Cancelled.
- [ ] Invariant: `done_at` set on entering Done, cleared when leaving completed state.
- [ ] Invariant: every task belongs to a project.
- [ ] `assigned_by`/`assigned_to` reference internal user IDs only.
- [ ] `Note` carries attachment references (image ref, filename, description, R2 key, user text) — never raw bytes.
- [ ] Human-review state lives in the workflow, not in `Status`.
- [ ] Unit tests for status transitions and `done_at` invariants.
