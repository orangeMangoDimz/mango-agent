---
phase: 3
order: "15"
mvp: true
title: PostgreSQL migrations (schema)
refs:
  - PRD §8.5
  - SDD §16 (ER diagram), §25.2
  - depends_on: [04]
---

# 15 — PostgreSQL migrations (schema)

Goal: Versioned migrations for the SDD §16 schema with FKs, constraints, and idempotency tables. Confirm values from task 04 first.

## Checklist

- [ ] Pick migration tool (e.g. yoyo/alembic); place files in `migrations/` ordered + versioned.
- [ ] `users` (uuid PK, display_name, timestamps).
- [ ] `provider_identities` (uuid PK, user_id FK, provider, provider_user_id, username, timestamps; unique(provider, provider_user_id)).
- [ ] `projects` (uuid PK, owner_user_id FK, title, timestamps; unique normalized title per owner if confirmed).
- [ ] `tasks` (uuid PK, project_id FK, title, description, priority, status, tags (json/array), assigned_by_user_id FK, assigned_to_user_id FK, note, created/updated/done_at).
- [ ] DB constraints for priority + status allowed values.
- [ ] `attachments` (uuid PK, uploader_user_id FK, task_id FK nullable, storage_provider, bucket_name, object_key, original_filename, mime_type, file_size, lifecycle_status, expires_at, timestamps).
- [ ] `idempotency_records` (uuid PK, user_id FK, provider, bot_instance, operation_key, operation_type, status, result_resource_id, created/completed_at; unique(provider, bot_instance, operation_key)).
- [ ] FKs + referential integrity; indexes on scoped query paths.
- [ ] Migrations run from a dedicated migration service, NOT every bot container.
- [ ] Integration test: apply from empty DB.
