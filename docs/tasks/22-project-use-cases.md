---
phase: 4
order: "22"
mvp: true
title: Project use cases (CRUD)
refs:
  - PRD §7.6, §14.1
  - SDD §14.2, §16.2
  - depends_on: [11, 16]
---

# 22 — Project use cases (CRUD)

Goal: Project CRUD with owner scope and a defined delete policy for existing tasks.

## Checklist

- [ ] `CreateProject`, `GetProject`, `SearchProjects`, `UpdateProject`, `DeleteProject`.
- [ ] All operations scoped to actor (owner).
- [ ] Project title normalization + per-owner uniqueness (per task 04 decision).
- [ ] Delete behavior defined: block/soft-delete/cascade per confirmed policy (SDD §16.2).
- [ ] Sensitive/irreversible delete requires confirmation flow (ties into 25/27).
- [ ] Return structured results, no DB rows leaked.
- [ ] Application tests: authorized CRUD + cross-user rejection.
