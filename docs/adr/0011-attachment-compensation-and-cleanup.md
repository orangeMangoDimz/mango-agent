---
id: ADR-11
title: Attachment compensation and cleanup strategy
status: Accepted
date: 2026-07-12
refs:
  - SDD §15
  - SDD §18
related:
  - docs/decisions/00-starting-values.md
---

# ADR-11 — Attachment compensation and cleanup strategy

## Context

R2 operations cannot participate in a PostgreSQL transaction, so partial failures can orphan objects or leave abandoned pending uploads. SDD §15 and §18.

## Decision

Use a **compensating lifecycle**: (1) upload object to R2, (2) persist pending metadata, (3) link metadata to the task inside the approved-task transaction, (4) on persistence failure after upload, mark/detect the object for cleanup, (5) cleanup is idempotent and safe to retry. Attachment `lifecycle_status` makes expired/orphaned/rejected objects visible to a cleanup worker.

## Consequences

- No half-finished tasks; R2 orphans are eventually reclaimed.
- Cleanup is idempotent and safe to retry across restarts.
- Soft-deleted tasks retain their attachments, which then follow the normal lifecycle.

## Cross-links

Task-04 confirmed values: pending attachment expiration **24h**; presigned URL **5 min**; supported images **JPEG, PNG, WebP**; image size **10 MiB**; **project deletion cascades soft-delete** and retains attachments.
ADR-05 (PostgreSQL metadata), ADR-07 (R2), ADR-10 (UoW), task 18 (R2 adapter), task 24 (attachment use cases), task 41 (cleanup worker).
