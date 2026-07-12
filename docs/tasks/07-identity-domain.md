---
phase: 1
order: "07"
mvp: true
title: Identity domain (User, ProviderIdentity)
refs:
  - PRD §8.1, §8.5
  - SDD §16.1, §19.1
---

# 07 — Identity domain (User, ProviderIdentity)

Goal: Pure domain entities for internal users and provider identities; identity-linking NOT required for v1.0.0.

## Checklist

- [ ] `User` entity: internal user ID, display name, created/updated at (immutable where applicable).
- [ ] `ProviderIdentity` entity: id, user_id, provider, provider_user_id, username, timestamps.
- [ ] Invariant: provider + provider_user_id is unique.
- [ ] Invariant: a provider identity belongs to exactly one internal user.
- [ ] Domain rule: provider metadata is trusted input, never model output.
- [ ] No infra imports; entities expose behavior, not bags of setters.
- [ ] Unit tests for uniqueness/equality invariants.
