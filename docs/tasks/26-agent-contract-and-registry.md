---
phase: 5
order: "26"
mvp: true
title: Agent contract & command-based registry
refs:
  - PRD §4.2(4), §15.3
  - SDD §4.6, §8 (Registry), §9
  - AGENTS.md (routing invariant)
---

# 26 — Agent contract & command-based registry

Goal: Common agent interface + deterministic command registry. NEVER LLM intent classification.

## Checklist

- [ ] Common `Agent` interface: accept normalized request + context, return provider-independent response.
- [ ] Command registry mapping: `task_management → TaskManagementAgent` (future `job_management → ...`).
- [ ] Channel instance supplies configured `agent_command` directly.
- [ ] Registry rejects unknown commands with actionable errors.
- [ ] No LLM in routing; routing logic not duplicated across channel adapters.
- [ ] Optional user-facing slash command support (not required).
- [ ] Unit tests: registry lookup + unknown-command rejection.
