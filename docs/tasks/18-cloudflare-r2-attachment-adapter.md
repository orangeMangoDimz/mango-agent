---
phase: 3
order: "18"
mvp: true
title: Cloudflare R2 attachment adapter
refs:
  - PRD §11.2, §11.4
  - SDD §18, §22.4
  - depends_on: [13]
---

# 18 — Cloudflare R2 attachment adapter

Goal: Implement attachment-storage port over private R2: upload, presign, retrieve, delete.

## Checklist

- [ ] Upload to private bucket; generate stable unique object key.
- [ ] Validate MIME (JPEG/PNG/WebP) + size (<=10 MiB) before upload.
- [ ] Short-lived presigned URL (5 min) only after authorization.
- [ ] Retrieve object/stream for provider delivery without exposing permanent URLs.
- [ ] Idempotent, retryable delete.
- [ ] Detect orphaned objects when persistence fails post-upload.
- [ ] No raw bytes or presigned URLs persisted anywhere.
- [ ] Integration test: upload/presign/delete + isolation (one user can't read another's object).
