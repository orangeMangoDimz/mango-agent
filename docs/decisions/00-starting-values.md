---
phase: 0
order: "00"
status: confirmed
confirmed_at: 2026-07-12
title: Confirmed starting values (task 04)
refs:
  - SDD §29 (recommended starting values)
  - SDD §31 (acceptance criteria)
  - SDD §16.2 (projects, deletion behavior)
  - SDD §19.3 (assignment)
  - SDD §19.4 (group conversations)
  - PRD §8.4 (priority/status field requirements)
  - docs/tasks/04-open-decisions.md
---

# 00 — Confirmed starting values

Locks the open product/engineering defaults from task 04 **before** migrations (task 15) and adapter contracts are finalized. Cross-cutting rationale for the items below will be recorded in the ADRs of task 05 — in particular ADR-11 (attachment compensation and cleanup) and ADR-12 (multi-user and group-conversation authorization model).

## Confirmed values

| Decision | Confirmed value | Deviates from SDD §29? |
| --- | --- | --- |
| Priority values | Low, Medium, High, Urgent | No |
| Status values | Todo, In progress, Blocked, Done, Cancelled | No |
| Project title uniqueness | Allow duplicate titles per owner | **Yes** |
| Default deletion | Soft delete for tasks and projects | No |
| Soft-delete retention | Indefinite; never auto-purged in v1 | No (confirms §29) |
| Project deletion → existing tasks | Cascade soft-delete all child tasks | No (defines §16.2) |
| Conversation state expiration | 24h after last activity | No |
| Proposal expiration | 2h | No |
| Pending attachment expiration | 24h | No |
| Presigned URL lifetime | 5 minutes | No |
| Supported images | JPEG, PNG, WebP | No |
| Image size limit | 10 MiB | No |
| Recent context | Bounded message window + structured references | No |
| Sensitive update confirmation | Ownership, assignee, project move, substantial content replacement | No |
| Concurrent conversation handling | Scoped lock + state version | No |
| Assignment model | Any resolved known internal user | No (defines §19.3) |
| Group-chat shared projects | Opt-in per group | No (defines §19.4) |

## Deviation from SDD §29

### Project title uniqueness

- SDD §29 recommends: **unique per owner after normalization** (reason: reduces ambiguous natural-language matching).
- Confirmed: **allow duplicate titles per owner**.
- Consequences:
  - Repository lookups by title return a collection; selection requires explicit user confirmation.
  - The task-management workflow's `AskForTarget` disambiguation path (SDD §12.2) must resolve multiple same-titled projects/tasks explicitly; never assume uniqueness when targeting by title.
  - Natural-language targeting stays unambiguous only when combined with another discriminator (e.g., last referenced project/task).
- Cross-link: ADR-12 (task 05), task 23 (task use cases), task 27 (workflow).

## Newly defined (previously open, not deviations)

### Project deletion — behavior for existing tasks (SDD §16.2)

- Confirmed: **cascade soft-delete all child tasks**.
- Consequences:
  - Soft-deleted tasks retain their attachments; attachments follow the normal soft-delete + cleanup lifecycle.
  - No hard delete in v1; retention is indefinite.
  - Restore semantics for a project with soft-deleted children are deferred to tasks 22/23.
- Cross-link: ADR-11 (task 05), task 22 (project use cases), task 41 (attachment cleanup worker).

### Soft-delete retention

- Confirmed: **indefinite; never auto-purged in v1**.
- Consequences:
  - Storage grows monotonically; a future purge job is intentionally out of scope for v1.
  - No retention SLA in v1.

### Assignment collaboration rule (SDD §19.3)

- Confirmed: a task may be assigned to **any internal user the application can resolve as a known internal user**.
- This defines the "approved collaboration rule" referenced by SDD §19.3: the assignment target must resolve to a known internal user.
- Invariants preserved:
  - The model may not mint a new assignee identity from a free-form name alone.
  - Model-produced user IDs remain untrusted input; the application resolves and authorizes.
- Cross-link: ADR-12 (task 05), task 21 (identity use cases), task 35 (authorization).

### Group conversations — shared project behavior (SDD §19.4)

- Confirmed: **shared project opt-in per group**.
- Consequences:
  - Requires an explicit opt-in record/flag tying a group conversation to a shared project.
  - Authorization rules must treat shared-project members as authorized readers/actors for that project's tasks within the group scope.
  - A message from one group member must still not inherit another member's pending proposal (SDD §19.4 invariant preserved).
- Cross-link: ADR-12 (task 05), task 35 (authorization).

## Sensitive update confirmation scope

- Confirmed scope (SDD §29): ownership change, assignee change, project move, substantial content replacement.
- "Substantial content replacement" defined for v1 as: **full replacement of the task title or the task description body**.
- Safe (no confirmation): adding or editing a note, tag changes, and other edits not listed above.
- Status transitions to Done/Cancelled are handled by their own use cases and are not classified as "sensitive update" here.
- Cross-link: task 23 (task use cases), task 27 (workflow).

## Values accepted as recommended (no deviation)

Priority values, status values, soft delete as the default deletion mode, conversation state expiration (24h), proposal expiration (2h), pending attachment expiration (24h), presigned URL lifetime (5 min), supported images (JPEG/PNG/WebP), image size limit (10 MiB), recent context (bounded message window + structured references), and concurrent conversation handling (scoped lock + state version) are all accepted exactly as recommended in SDD §29.

## Downstream impact

- Task 08 (task-management domain): priority/status enums match the confirmed values.
- Task 15 (migrations): add CHECK constraints for priority/status; add soft-delete columns (`deleted_at`) on projects and tasks; project deletion cascades soft-delete to tasks in one transaction (Unit of Work, task 11).
- Task 22/23 (project/task use cases): title lookup returns collections + disambiguation; project delete cascades soft-delete; sensitive-update guard uses the scope above.
- Task 35 (authorization): assignment rule + group shared-project opt-in.
- Task 05 (ADRs): ADR-11 and ADR-12 must cross-link to this document.
