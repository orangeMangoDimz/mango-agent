---
phase: 0
order: "04"
mvp: true
title: Open decisions — confirm starting values
refs:
  - SDD §29 (recommended starting values)
  - SDD §31 (acceptance criteria)
  - PRD §8.4 (priority/status)
---

# 04 — Open decisions — confirm starting values

Goal: Confirm the open product/engineering defaults BEFORE migrations (15) and adapter contracts are finalized. Capture results as ADRs (05).

## Checklist

- [ ] Priority values: Low, Medium, High, Urgent.
- [ ] Status values: Todo, In progress, Blocked, Done, Cancelled.
- [ ] Project title uniqueness: unique per owner after normalization (open).
- [ ] Default deletion: soft delete for tasks and projects (confirm retention policy).
- [ ] Conversation state expiration: 24h after last activity.
- [ ] Proposal expiration: 2h.
- [ ] Pending attachment expiration: 24h.
- [ ] Presigned URL lifetime: 5 minutes.
- [ ] Supported images: JPEG, PNG, WebP.
- [ ] Image size limit: 10 MiB.
- [ ] Recent context: bounded message window + structured references.
- [ ] Sensitive update confirmation scope: ownership, assignee, project move, substantial content replacement.
- [ ] Concurrent conversation handling: scoped lock + state version.
- [ ] Assignment + group-chat collaboration model (SDD §19.3, §19.4).
- [ ] Project deletion behavior for existing tasks (SDD §16.2).
- [ ] Document confirmed values; flag any deviation from SDD §29.
