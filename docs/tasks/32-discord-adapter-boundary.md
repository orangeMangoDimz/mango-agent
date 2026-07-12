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

- [x] Discord gateway event handling boundary.
- [x] Reuse inbound/outbound normalized contracts from task 30.
- [x] Map Discord user → internal user via identity use case.
- [x] Provider-specific formatting + thread/reply handling.
- [x] No business rules in adapter.
- [x] Contract tests with Discord event fixtures + fake agent.
- [x] Boundary lives in a separate gateway service; does not block MVP.
