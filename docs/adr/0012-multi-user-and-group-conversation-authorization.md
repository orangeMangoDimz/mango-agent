---
id: ADR-12
title: Multi-user and group-conversation authorization model
status: Accepted
date: 2026-07-12
refs:
  - SDD §19
  - SDD §22.3
related:
  - docs/decisions/00-starting-values.md
---

# ADR-12 — Multi-user and group-conversation authorization model

## Context

Mango is multi-user and operates in provider group chats. User scope must never be inferred from model output, and cross-user data leakage is a critical risk (SDD §19, §22.3, §30).

## Decision

Every use case receives an **immutable actor context** created from provider-authenticated metadata; model-produced user/owner/provider IDs are untrusted input. Repository reads are scoped by actor or by an explicitly evaluated collaboration rule — lookup by globally unique ID is not sufficient authorization. Search results are filtered before return. Attachment retrieval authorizes through its task or explicit ownership. A message from one group member never inherits another member's pending proposal.

Assignment (SDD §19.3): a task may be assigned to any internal user the application can resolve as a **known internal user**; the model may not mint a new assignee from a free-form name. Group conversations (SDD §19.4): **shared projects are opt-in per group** via an explicit opt-in record.

## Consequences

- Cross-user leakage prevented; verified by security isolation tests (task 40).
- Group shared-project opt-in requires an explicit record and authorization rule for shared-project members within the group scope.
- Because project titles may duplicate, targeting by title returns a collection and requires explicit disambiguation — uniqueness is never assumed.
- Sensitive updates (ownership, assignee, project move, full title/description replacement) require confirmation.

## Cross-links

Task-04 confirmed values: **assignment to any resolved known internal user**; **group shared-project opt-in per group**; **duplicate project titles per owner** → disambiguation; **sensitive-update confirmation scope**.
ADR-05 (scoped queries), ADR-08 (proposal isolation), task 21 (identity use cases), task 35 (authorization), task 40 (security isolation tests).
