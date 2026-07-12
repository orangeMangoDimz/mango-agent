---
id: ADR-03
title: Direct in-process communication without an internal API
status: Accepted
date: 2026-07-12
refs:
  - SDD §5
  - SDD §8
  - SDD §2.2
---

# ADR-03 — Direct in-process communication without an internal API

## Context

v1.0.0 explicitly excludes a public or internal general-purpose HTTP API (SDD §2.2). All components run inside one bot process.

## Decision

Adapters, agents, application use cases, and ports call each other **directly in-process**. No internal HTTP bus, RPC, or message broker between them.

## Consequences

- No network overhead, serialization, or internal-network failure modes.
- Simpler testing and tracing within a process.
- Sub-parts cannot be scaled independently; future extraction (SDD §26.3) would require an explicit ADR and must not change domain contracts.
- Agents still never touch infrastructure directly — they call application use cases through tools (SDD §4.4).

## Cross-links

ADR-01 (modular monolith), ADR-04 (dependency direction).
