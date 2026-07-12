---
phase: 0
order: "05"
mvp: true
title: Architecture Decision Records
refs:
  - SDD §28 (12 ADRs)
---

# 05 — Architecture Decision Records

Goal: Capture the 12 ADRs from SDD §28 in `docs/adr/`, one file each, referencing rationale + consequences.

## Checklist

- [x] ADR template (context, decision, consequences, status) — [docs/adr/0000-template.md](../adr/0000-template.md).
- [x] ADR-01 Modular monolith vs microservices.
- [x] ADR-02 One runtime per channel-agent configuration.
- [x] ADR-03 Direct in-process communication without internal API.
- [x] ADR-04 Hexagonal Architecture and dependency rules.
- [x] ADR-05 PostgreSQL as durable source of truth.
- [x] ADR-06 Redis as temporary conversation/workflow state.
- [x] ADR-07 Private R2 attachment storage.
- [x] ADR-08 LangGraph workflow and checkpoint strategy.
- [x] ADR-09 Command-based agent registry without LLM routing.
- [x] ADR-10 Unit of Work and idempotent mutation strategy.
- [x] ADR-11 Attachment compensation and cleanup strategy.
- [x] ADR-12 Multi-user and group-conversation authorization model.
- [x] Cross-link ADRs to the confirmed values from task 04 — explicit on ADR-05/10/11/12; see [docs/adr/](../adr/) and [docs/decisions/00-starting-values.md](../decisions/00-starting-values.md).
