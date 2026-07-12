---
id: ADR-01
title: Modular monolith versus microservices
status: Accepted
date: 2026-07-12
refs:
  - SDD §4.1
  - SDD §5
  - SDD §2.2
  - SDD §26.3
---

# ADR-01 — Modular monolith versus microservices

## Context

v1.0.0 is a single-user-scale personal agent with no public/internal HTTP API (SDD §2.2) and a small operational footprint. The system still needs strong module boundaries so provider and infrastructure concerns stay replaceable. Full SDD rationale in §4.1 and §5.

## Decision

Build Mango Agent as a **Python modular monolith**: one application with modules that own their behavior and contracts, deployed as multiple processes (one per bot instance). Not microservices.

## Consequences

- Atomic refactoring across modules; simpler dependency management and ops.
- No distributed-system failure modes inside one bot runtime.
- Risk: boundary erosion over time — mitigated by public module contracts, dependency-rule guard tests, and these ADRs.
- Module extraction (SDD §26.3) only when operational evidence requires it, and only via an explicit architecture decision.

## Cross-links

ADR-02 (runtime isolation), ADR-03 (in-process communication), ADR-04 (hexagonal + dependency rules).
