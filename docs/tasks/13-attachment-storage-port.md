---
phase: 2
order: "13"
mvp: true
title: Attachment storage port (R2)
refs:
  - PRD §11.2, §15.6
  - SDD §18, §22.4
---

# 13 — Attachment storage port (R2)

Goal: Dedicated attachment-storage port for private object upload, authorized retrieval, and deletion.

## Checklist

- [ ] `AttachmentStorage` port: upload (returns stable object key), delete, generate short-lived presigned URL, retrieve object for provider delivery.
- [ ] Upload validation inputs: supported MIME (JPEG/PNG/WebP), max size (10 MiB), provider download success.
- [ ] Object key generation owned by port/adapter; original filename is metadata only.
- [ ] Presigned URL only after authorization; lifetime 5 min; never persisted.
- [ ] Bucket stays private; no permanent public URLs.
- [ ] Deletion is idempotent + safe to retry.
- [ ] No R2 SDK types in the port.
