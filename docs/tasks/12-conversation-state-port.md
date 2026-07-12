---
phase: 2
order: "12"
mvp: true
title: Conversation state port (Redis)
refs:
  - PRD §10, §15.6
  - SDD §17 (Redis), §15.6
---

# 12 — Conversation state port (Redis)

Goal: Dedicated conversation-state port (NOT a generic DB abstraction) for expiring workflow + proposal state.

## Checklist

- [ ] `ConversationStateStore` port: load, save (with expiration), clear.
- [ ] `ProposalStore` port: create proposal (with version), get, consume approval atomically, clear.
- [ ] `ConfirmationStore` port: create/get/consume confirmation.
- [ ] State key scope encodes provider, bot instance, conversation/thread, internal user, agent command.
- [ ] Port methods accept scoped key + version for optimistic concurrency.
- [ ] No Redis client types in the port.
- [ ] Port docstring states expiration semantics (proposal 2h, state 24h, attachment 24h).
