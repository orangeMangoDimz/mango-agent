---
phase: 1
order: "10"
mvp: true
title: Conversation domain (proposal/confirmation state types)
refs:
  - PRD §10, §13.1
  - SDD §12.1, §17.2, §13.1
---

# 10 — Conversation domain (proposal/confirmation state types)

Goal: Pure domain types for temporary conversation context, pending proposals, and confirmations (Redis is only one possible store).

## Checklist

- [ ] `ConversationState` value type: user/provider identity, recent bounded messages, last project/task refs, temp attachment IDs, LangGraph checkpoint ref, timestamps.
- [ ] `PendingProposal`: operation ID, version, proposal content, attachment IDs, created/expires_at.
- [ ] `PendingConfirmation`: operation ID, operation type, target ref, expires_at.
- [ ] Approval invariants encoded: same user, bot+conversation scope, active proposal/operation id, not expired, not consumed, content unchanged since approval.
- [ ] Revision = new proposal version, invalidates prior approval.
- [ ] Expiration rules: expired proposal cannot be approved.
- [ ] Unit tests for proposal version invalidation + expiration.
