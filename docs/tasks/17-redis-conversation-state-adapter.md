---
phase: 3
order: "17"
mvp: true
title: Redis conversation-state adapter
refs:
  - PRD §10, §15.6
  - SDD §17, §20.3
  - depends_on: [12]
---

# 17 — Redis conversation-state adapter

Goal: Implement conversation/proposal/confirmation state ports over Redis with scoped keys + expiration + optimistic versioning.

## Checklist

- [ ] Implement `ConversationStateStore` (load/save/clear) with TTL 24h.
- [ ] Implement `ProposalStore` (create versioned, get, atomic consume, clear) with TTL 2h.
- [ ] Implement `ConfirmationStore` with TTL.
- [ ] State key includes provider, bot instance, conversation/thread, internal user, agent command.
- [ ] Atomic compare-and-set on state version for concurrent-message protection.
- [ ] Short-lived scoped processing lock around state transitions.
- [ ] Expiration: pending proposal unapprovable after expiry; temp attachments eligible for cleanup.
- [ ] Integration test: isolation across users/bots/threads; expiration behavior.
