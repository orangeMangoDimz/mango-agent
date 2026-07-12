---
phase: 7
order: "33"
mvp: true
title: Composition root, startup & graceful shutdown
refs:
  - PRD §4.2(10), §15.8, §16.4
  - SDD §7.2, §25.3, §25.4
  - depends_on: [03, 16, 17, 18, 19, 20, 26, 31]
---

# 33 — Composition root, startup & graceful shutdown

Goal: One bootstrap that constructs all concrete adapters via DI, validates readiness, and shuts down cleanly.

## Checklist

- [ ] Single composition root builds: channels, agent registry + task agent, use cases, repos, UoW, Redis/R2/Anthropic/tracing adapters.
- [ ] Dependencies injected via constructors; no internal construction of infra clients.
- [ ] Construct ONLY the configured agent + its deps per bot service.
- [ ] Fail fast on missing/invalid config; verify PG/Redis/R2/model connectivity before polling.
- [ ] Health/readiness reporting.
- [ ] Graceful shutdown: stop polling → finish/cancel active op → release locks → flush logs/traces → close clients.
- [ ] Migrations excluded from bot startup (run by dedicated service).
- [ ] Restart-during-pending-approval handled safely (state in Redis).
- [ ] Smoke test: bring up `mango-task-telegram` end-to-end in compose.
