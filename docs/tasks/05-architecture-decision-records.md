---
phase: 0
order: "05"
mvp: true
title: Architecture Decision Records
refs:
  - SDD §28 (12 ADRs)
---

# 05 — Architecture Decision Records

Goal: Capture the 12 ADRs from SDD §28 in `docs/adr/` (or `docs/decisions/`), one file each, referencing rationale + consequences.

## Checklist

- [ ] ADR template (context, decision, consequences, status).
- [ ] ADR-01 Modular monolith vs microservices.
- [ ] ADR-02 One runtime per channel-agent configuration.
- [ ] ADR-03 Direct in-process communication without internal API.
- [ ] ADR-04 Hexagonal Architecture and dependency rules.
- [ ] ADR-05 PostgreSQL as durable source of truth.
- [ ] ADR-06 Redis as temporary conversation/workflow state.
- [ ] ADR-07 Private R2 attachment storage.
- [ ] ADR-08 LangGraph workflow and checkpoint strategy.
- [ ] ADR-09 Command-based agent registry without LLM routing.
- [ ] ADR-10 Unit of Work and idempotent mutation strategy.
- [ ] ADR-11 Attachment compensation and cleanup strategy.
- [ ] ADR-12 Multi-user and group-conversation authorization model.
- [ ] Cross-link ADRs to the confirmed values from task 04.
