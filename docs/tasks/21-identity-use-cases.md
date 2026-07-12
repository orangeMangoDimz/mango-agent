---
phase: 4
order: "21"
mvp: true
title: Identity use cases (resolve provider identity)
refs:
  - PRD §8.1, §14.4
  - SDD §14.1, §19.1
  - depends_on: [11, 16]
---

# 21 — Identity use cases (resolve provider identity)

Goal: Resolve a provider-authenticated identity to an internal user and produce an immutable actor context.

## Checklist

- [ ] `ResolveProviderIdentity` use case: find-or-create internal user + provider identity mapping.
- [ ] Produce immutable authenticated execution context (internal user id, bot instance, conversation scope).
- [ ] Block overriding provider metadata with model output.
- [ ] `GetUser` / `SearchKnownUsers` for assignment, with assignment-eligibility rule (SDD §19.3).
- [ ] Use Unit of Work for create-user-with-identity atomicity.
- [ ] Application tests with in-memory repos + fakes; cross-user rejection covered.
