---
phase: 6
order: "32"
mvp: false
title: Discord adapter boundary
refs:
  - PRD §12.1
  - SDD §2.1 (reusable boundary), §8.1
  - depends_on: [30]
---

# 32 — Discord adapter boundary `[SEC]`

Goal: Secondary channel. Reuse the same normalized contracts as Telegram; full parity not required for v1.0.0.

## Checklist

- [ ] Discord gateway event handling boundary.
- [ ] Reuse inbound/outbound normalized contracts from task 30.
- [ ] Map Discord user → internal user via identity use case.
- [ ] Provider-specific formatting + thread/reply handling.
- [ ] No business rules in adapter.
- [ ] Contract tests with Discord event fixtures + fake agent.
- [ ] Behind a feature flag / separate service; does not block MVP.
