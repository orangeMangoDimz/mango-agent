---
id: ADR-02
title: One runtime per channel-agent configuration
status: Accepted
date: 2026-07-12
refs:
  - SDD §7
  - SDD §5
  - SDD §26.2
---

# ADR-02 — One runtime per channel-agent configuration

## Context

Each bot needs independent credentials, restart cycles, scaling, and failure isolation, while sharing PostgreSQL, Redis, and R2. SDD §7 and §5.

## Decision

Run **one Docker Compose service per configured channel-agent combination** (e.g. `task-telegram`, `task-discord`). All services reuse a single image and the monorepo source. Channel and agent command are selected at startup via environment configuration.

## Consequences

- Independent failure, restart, and credential isolation per bot.
- N processes share PG/Redis/R2 — database connection budget must account for every service (SDD §26.2).
- Telegram long-polling requires coordination if horizontally scaled (SDD §26.2); v1 scales vertically + per-instance.
- Adding a bot = new compose service + env, no code change.

## Cross-links

ADR-01 (modular monolith), ADR-09 (command registry selects agent), task 02 (compose), task 33 (composition root).
