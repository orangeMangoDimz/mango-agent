---
phase: 4
order: "25"
mvp: true
title: Conversation workflow use cases (state + proposals)
refs:
  - PRD §10, §13.1
  - SDD §14.5, §17, §20.3
  - depends_on: [12, 17]
---

# 25 — Conversation workflow use cases (state + proposals)

Goal: Load/save scoped conversation state and manage pending proposals/confirmations with atomic approval consumption.

## Checklist

- [ ] `LoadScopedState` / `SaveScopedState` (with expiration + version).
- [ ] `CreatePendingProposal` (operation ID + version + attachment IDs).
- [ ] `ConsumeProposalApproval`: atomic, single-use, validates invariants (same user/scope/op, not expired, content unchanged).
- [ ] `ReviseProposal`: new version invalidates prior approval.
- [ ] `CreatePendingConfirmation` / `ConsumeConfirmation` for sensitive update + delete.
- [ ] `ClearCompletedOrRejectedState`.
- [ ] Expired proposal: refuse approval, offer rebuild from context.
- [ ] Application tests: revision invalidation, expiration, atomic single-use consume.
