---
phase: 6
order: "31"
mvp: true
title: Telegram adapter (long polling, text, images, delivery)
refs:
  - PRD §12, §16.1
  - SDD §8.1 (channel adapters), §11
  - depends_on: [21, 30, 33]
---

# 31 — Telegram adapter (long polling, text, images, delivery)

Goal: Primary v1.0.0 channel: long polling, text + image input, identity mapping, normalized calls, formatted delivery.

## Checklist

- [x] Long-polling receiver for text + image attachments.
- [x] Map Telegram user → internal user via identity use case.
- [x] Convert provider event → normalized inbound message; preserve provider event id for idempotency.
- [x] Download provider attachments for upload to R2 (via attachment use case).
- [x] Attach configured `agent_command` and call agent in-process.
- [x] Render follow-up questions, task proposals, approval/revision/reject prompts.
- [x] Return task query results + associated images (presigned, authorized).
- [x] Provider-specific message formatting + reply-to handling.
- [x] No task-management business rules in adapter.
- [x] Contract tests with Telegram event fixtures + fake agent.
