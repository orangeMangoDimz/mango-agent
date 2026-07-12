---
phase: 5
order: "29"
mvp: true
title: Graph limits & retry bounds
refs:
  - PRD §9
  - SDD §12.4, §21
---

# 29 — Graph limits & retry bounds

Goal: Enforce bounded execution to prevent loops/excess cost; explicit terminal handling.

## Checklist

- [ ] Max model turns per inbound message (configurable).
- [ ] Max tool calls per execution.
- [ ] Bounded repair attempts for invalid structured tool arguments.
- [ ] Explicit terminal handling when limits reached (clear user-facing message, trace failure).
- [ ] No automatic unbounded loops.
- [ ] Invalid model tool args → structured validation error back to graph → follow-up if still invalid.
- [ ] Limits tunable via config; tune via LangSmith traces.
- [ ] Agent tests: max-step termination + invalid-arg repair.
