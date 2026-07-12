---
phase: 9
order: "40"
mvp: true
title: Security isolation tests
refs:
  - PRD §18
  - SDD §24.6, §19, §22
  - depends_on: [35]
---

# 40 — Security isolation tests

Goal: Critical security property: User A can never receive/mutate/delete/infer User B's protected data.

## Checklist

- [ ] Cross-user read rejection (tasks, projects, attachments).
- [ ] Cross-user update/delete rejection.
- [ ] Cross-user attachment retrieval rejection (presign/authz).
- [ ] Model-invented identifiers/owners rejected by application tools.
- [ ] Image/text instructions cannot override authorization or tool policy.
- [ ] Group conversation: no proposal inheritance across members.
- [ ] Parameterized over every read/update/delete/reference/attachment path.
