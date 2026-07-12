---
id: ADR-06
title: Redis as temporary conversation and workflow state
status: Accepted
date: 2026-07-12
refs:
  - SDD §4.5
  - SDD §17
  - SDD §21
related:
  - docs/decisions/00-starting-values.md
---

# ADR-06 — Redis as temporary conversation and workflow state

## Context

The agent needs expiring conversation context and fast workflow checkpoint access, separate from durable business data. SDD §4.5 and §17.

## Decision

Redis stores **scoped conversation state, pending proposals/confirmations, and LangGraph checkpoints only** — never tasks, projects, identities, or attachment ownership. State keys scope by provider/bot instance/conversation/user/agent command (SDD §17.1).

## Consequences

- Fail closed for approval-dependent flows when Redis is unavailable (SDD §21); durable data stays safe.
- Scoped keys prevent leakage between users, bots, channels, threads, and agent types.
- Expiration invalidates pending proposals and makes temporary attachments eligible for cleanup.

## Cross-links

Task-04 confirmed values: conversation state **24h** after last activity; proposal **2h**; pending attachment **24h**.
ADR-08 (LangGraph checkpoints), ADR-11 (cleanup), task 17 (Redis adapter).
