---
phase: 6
order: "30"
mvp: true
title: Normalized message contracts (inbound/outbound)
refs:
  - PRD §12, §16.2, §16.3
  - SDD §10
---

# 30 — Normalized message contracts (inbound/outbound)

Goal: Provider-independent inbound/outbound contracts shared by Telegram + Discord.

## Checklist

- [ ] Inbound: provider, bot instance, provider event id, conversation id, thread id, provider user id, display name/username, message id, text, attachment descriptors, reply-to ref, received timestamp.
- [ ] Outbound capabilities: text, image/attachment, provider-supported approval actions, reply-to ref, delivery metadata.
- [ ] Attachment descriptor carries `storage_id` (attachment id), not bytes.
- [ ] Contracts live in `channels/` (or shared channel-contracts module); agent never sees provider SDK objects.
- [ ] Response types: final text, follow-up, proposal, confirmation, task list/details, attachment ref, error.
- [ ] Unit tests on contract serialization.
