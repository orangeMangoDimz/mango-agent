---
phase: 4
order: "24"
mvp: true
title: Attachment use cases (register, link, authorize, presign)
refs:
  - PRD §11, §14.3
  - SDD §13, §14.4, §15 (compensation), §18.3
  - depends_on: [13, 16, 18]
---

# 24 — Attachment use cases (register, link, authorize, presign)

Goal: Attachment workflow with compensating lifecycle (R2 can't join PG transaction) and authorized retrieval.

## Checklist

- [ ] `RegisterPendingUpload`: validate, upload to R2, persist pending metadata, return attachment ID.
- [ ] `LinkAttachmentToTask`: link metadata to task inside the approved-task transaction.
- [ ] `AuthorizeRetrieval`: resolve user → load metadata via authorized query → verify task/project access.
- [ ] `GenerateAccess`: short-lived presigned URL or stream for provider delivery (5 min, never persisted).
- [ ] `RejectOrExpireAttachment`: move to cleanup-eligible lifecycle.
- [ ] Compensation: if persistence fails after upload, mark/detect orphan for cleanup.
- [ ] Reject/cancel path triggers cleanup (ties to 41).
- [ ] Application tests: link + cleanup compensation, cross-user retrieval rejection.
