---
phase: 8
order: "35"
mvp: true
title: Multi-user authorization & data isolation
refs:
  - PRD §6.2, §18
  - SDD §19, §22.3
  - AGENTS.md (user-scope invariant)
  - depends_on: [16, 21, 24]
---

# 35 — Multi-user authorization & data isolation

Goal: Every operation scoped to an authenticated internal user; no cross-user leakage; model output untrusted.

## Checklist

- [ ] Immutable actor context on every use case; user scope never from model output.
- [ ] Repository reads/writes take actor scope or authorization spec.
- [ ] Lookup by global ID is NOT sufficient authorization.
- [ ] Search results filtered before returning to agent.
- [ ] Attachment retrieval authorized via task/ownership relation.
- [ ] Assignment policy (SDD §19.3): self always; other only if resolvable known internal user + allowed rule; no free-form-name new assignee.
- [ ] Group conversations: conversation scope + actor scope; no proposal inheritance across members.
- [ ] Prompt/tool safety: image/text cannot override authorization or tool policy.
- [ ] Security tests: User A cannot read/update/delete/infer User B's data (task 40).
