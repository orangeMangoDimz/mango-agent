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

- [ ] Long-polling receiver for text + image attachments.
- [ ] Map Telegram user → internal user via identity use case.
- [ ] Convert provider event → normalized inbound message; preserve provider event id for idempotency.
- [ ] Download provider attachments for upload to R2 (via attachment use case).
- [ ] Attach configured `agent_command` and call agent in-process.
- [ ] Render follow-up questions, task proposals, approval/revision/reject prompts.
- [ ] Return task query results + associated images (presigned, authorized).
- [ ] Provider-specific message formatting + reply-to handling.
- [ ] No task-management business rules in adapter.
- [ ] Contract tests with Telegram event fixtures + fake agent.
