---
phase: 9
order: "38"
mvp: true
title: Contract tests (adapter contracts)
refs:
  - PRD §18.2
  - SDD §24.4
  - depends_on: [16, 17, 18, 19, 31, 32]
---

# 38 — Contract tests (adapter contracts)

Goal: Verify each adapter satisfies its port contract.

## Checklist

- [ ] Telegram normalization + delivery contract.
- [ ] Discord normalization + delivery contract.
- [ ] PostgreSQL repository contracts (scoped access, mapping, constraints).
- [ ] Redis state serialization + expiration + isolation.
- [ ] R2 upload/authorization/deletion contract.
- [ ] Anthropic model adapter request/response mapping.
- [ ] Shared contract base classes so the same suite runs against fakes + real adapters.
