---
id: ADR-09
title: Command-based agent registry without LLM routing
status: Accepted
date: 2026-07-12
refs:
  - SDD §4.6
  - SDD §5
  - SDD §2.2
---

# ADR-09 — Command-based agent registry without LLM routing

## Context

Agent selection must be deterministic and cheap. SDD §2.2 excludes LLM-based routing between agent types; §4.6 requires configuration-based selection.

## Decision

A bot service is configured with one **agent command** (e.g. `task_management`). An agent **registry resolves that command to a concrete agent implementation**. No LLM decides which agent type runs.

## Consequences

- Predictable, low-cost, easily testable routing.
- Adding an agent = a new command + registry entry, not a model prompt change.
- Cannot auto-dispatch unsupported intents; unsupported operations are handled inside the chosen agent's workflow (SDD §12.2).

## Cross-links

ADR-02 (runtime configures the command), ADR-08 (workflow), task 26 (agent contract + registry).
