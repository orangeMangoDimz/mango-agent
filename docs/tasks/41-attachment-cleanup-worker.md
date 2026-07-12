---
phase: 10
order: "41"
mvp: true
title: Attachment cleanup worker
refs:
  - PRD §11.2 (delete abandoned)
  - SDD §15 (compensation), §18 (lifecycle), §26.3
  - depends_on: [18, 24]
---

# 41 — Attachment cleanup worker

Goal: Idempotent cleanup of rejected/expired/orphaned R2 objects + metadata.

## Checklist

- [ ] Scheduled/task-based worker (separate from bot service) scanning cleanup-eligible attachments.
- [ ] Delete R2 object (idempotent, retryable) + update metadata lifecycle → Deleted.
- [ ] Handle CleanupPending retryable failures.
- [ ] Orphan detection when persistence failed post-upload.
- [ ] Respect R2 retention/lifecycle rules.
- [ ] Metrics: pending/orphaned attachment counts, cleanup failures.
- [ ] Tests: cleanup after reject/expire/orphan; idempotent re-run.
