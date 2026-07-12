---
phase: 5
order: "28"
mvp: true
title: Agent tool adapters (project/task/attachment/identity)
refs:
  - PRD §14 (tools), §15.4
  - SDD §12.3 (tool boundaries), §22.3
  - depends_on: [21, 22, 23, 24]
---

# 28 — Agent tool adapters (project/task/attachment/identity)

Goal: Tools expose application use cases to the graph; allow-listed per agent/state; structured in/out.

## Checklist

- [ ] Project tools: create/get/search/update/delete.
- [ ] Task tools: validate proposal, approved create, get, search, update, status transition, confirmed delete.
- [ ] Attachment tools: upload, get metadata, presign/retrieve, associate with task, delete temp.
- [ ] User tools: resolve provider user, get user, search known users for assignment.
- [ ] Each tool: structured input/output, validate acting user, enforce user isolation, actionable errors.
- [ ] Tools call use cases, never repositories/SQL/R2/Redis directly.
- [ ] Model cannot select arbitrary repo/SQL/object key/user scope.
- [ ] Tool allow-list per agent + workflow state.
- [ ] Tools independently testable + reusable by future MCP.
