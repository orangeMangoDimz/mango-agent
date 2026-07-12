---
phase: 0
order: "03"
mvp: true
title: Configuration, env & secrets (fail-fast)
refs:
  - PRD §17.1
  - SDD §7.1, §7.2, §22.1
---

# 03 — Configuration, env & secrets (fail-fast)

Goal: Typed config object loaded from env, validated at startup; secrets never logged or committed.

## Checklist

- [ ] Define a config dataclass for: channel provider + bot creds, agent command, model selection, PG/Redis/R2, LangSmith, logging/env.
- [ ] Load from environment with validation; fail fast with actionable errors on missing/invalid.
- [ ] Add `.env.example` documenting every var (no real secrets).
- [ ] Secrets sourced only from env/deployment config — never in repo, logs, or traces.
- [ ] Redact secrets from structured logs by default.
- [ ] `shared/` config loader has unit tests for missing/invalid cases.
