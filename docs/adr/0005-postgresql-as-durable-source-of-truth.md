---
id: ADR-05
title: PostgreSQL as durable source of truth
status: Accepted
date: 2026-07-12
refs:
  - SDD §4.5
  - SDD §16
  - SDD §25.5
related:
  - docs/decisions/00-starting-values.md
---

# ADR-05 — PostgreSQL as durable source of truth

## Context

The system needs durable relational data with transactions, referential integrity, and flexible filtering. Redis and R2 must not be the only record of a completed business operation. SDD §4.5 and §16.

## Decision

PostgreSQL is the **durable source of truth** for users, provider identities, projects, tasks, attachment metadata, and idempotency records. Schema evolves via ordered, versioned migrations. Multi-repository mutations commit through a Unit of Work (ADR-10).

## Consequences

- ACID transactions for cross-repo mutations; scheduled backup + tested restore required (SDD §25.5).
- Database constraints enforce enums, foreign keys, and soft-delete columns.
- Redis/R2 loss never loses a completed business operation; fail-closed for approval-dependent flows.

## Cross-links

Task-04 confirmed values: soft delete + **indefinite retention** on projects and tasks; **project deletion cascades soft-delete** to child tasks in one transaction; priority/status **CHECK constraints** (Low/Medium/High/Urgent; Todo/In progress/Blocked/Done/Cancelled).
ADR-10 (UoW + idempotency), task 15 (migrations), task 16 (repository adapters).
