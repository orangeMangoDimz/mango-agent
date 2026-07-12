---
id: ADR-04
title: Hexagonal Architecture and dependency rules
status: Accepted
date: 2026-07-12
refs:
  - SDD §4.2
  - SDD §9
  - AGENTS.md (dependency direction, invariants)
---

# ADR-04 — Hexagonal Architecture and dependency rules

## Context

Business behavior must stay independent of Telegram, Discord, PostgreSQL, Redis, R2, Anthropic, and LangSmith so it is testable and replaceable. SDD §4.2 and §9.

## Decision

Apply **Hexagonal Architecture (Ports & Adapters)** with dependency direction `Channels → Agents → Application → Domain/Ports ← Adapters`. Inner layers never import Telegram/Discord/Postgres/Redis/R2/Anthropic/LangSmith. Only the composition root selects concrete implementations.

## Consequences

- Domain/application independently testable; providers and infra swappable.
- Enforced by a dependency-rule guard test (task 01; `tests/unit/test_dependency_rules.py`).
- Risk: erosion — mitigated by the guard test, public module contracts, and ADR-04 itself.

## Cross-links

ADR-01, ADR-03, task 01 (repo scaffolding + guard test), `tests/unit/test_dependency_rules.py`.
