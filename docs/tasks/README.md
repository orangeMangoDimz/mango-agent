# Mango Agent — Implementation Tasks

Whole v1.0.0 requirement broken into small, ordered, MVP-first tasks. One file per task; each file is a checklist.

Source of truth: `docs/PRD.md` (v1.0.0), `docs/SYSTEM_DESIGN.md` (v0.3.0), `AGENTS.md`.

Legend:
- `[MVP]` — required for the v1.0.0 working Telegram task-management bot.
- `[SEC]` — secondary / post-MVP boundary (still in scope, lower priority).

Conventions: Hexagonal Architecture, `uv`, dependency direction `Channels → Agents → Application → Domain/Ports ← Adapters`. Inner layers never import Telegram/Discord/Postgres/Redis/R2/Anthropic/LangSmith.

## Phase 0 — Foundation & Decisions

- [ ] [01 — Repo scaffolding, tooling & folder structure](01-repo-scaffolding.md) `[MVP]`
- [ ] [02 — Docker Compose local dev (Postgres + Redis)](02-docker-compose-local-dev.md) `[MVP]`
- [ ] [03 — Configuration, env & secrets (fail-fast)](03-configuration-and-secrets.md) `[MVP]`
- [x] [04 — Open decisions: confirm starting values](04-open-decisions.md) `[MVP]`
- [ ] [05 — Architecture Decision Records](05-architecture-decision-records.md) `[MVP]`

## Phase 1 — Shared & Domain (no infra)

- [ ] [06 — Shared kernel (IDs, errors, value objects)](06-shared-kernel.md) `[MVP]`
- [ ] [07 — Identity domain (User, ProviderIdentity)](07-identity-domain.md) `[MVP]`
- [ ] [08 — Task management domain (Project, Task, enums, invariants)](08-task-management-domain.md) `[MVP]`
- [ ] [09 — Attachments domain (Attachment, lifecycle)](09-attachments-domain.md) `[MVP]`
- [ ] [10 — Conversation domain (proposal/confirmation state types)](10-conversation-domain.md) `[MVP]`

## Phase 2 — Ports (interfaces)

- [ ] [11 — Repository ports + Unit of Work](11-repository-ports-and-uow.md) `[MVP]`
- [ ] [12 — Conversation state port (Redis)](12-conversation-state-port.md) `[MVP]`
- [ ] [13 — Attachment storage port (R2)](13-attachment-storage-port.md) `[MVP]`
- [ ] [14 — Model port + tracing port](14-model-and-tracing-ports.md) `[MVP]`

## Phase 3 — Infrastructure adapters

- [ ] [15 — PostgreSQL migrations (schema)](15-postgresql-migrations.md) `[MVP]`
- [ ] [16 — PostgreSQL repository adapters](16-postgresql-repository-adapters.md) `[MVP]`
- [ ] [17 — Redis conversation-state adapter](17-redis-conversation-state-adapter.md) `[MVP]`
- [ ] [18 — Cloudflare R2 attachment adapter](18-cloudflare-r2-attachment-adapter.md) `[MVP]`
- [ ] [19 — Anthropic model adapter](19-anthropic-model-adapter.md) `[MVP]`
- [ ] [20 — LangSmith tracing integration](20-langsmith-tracing-integration.md) `[MVP]`

## Phase 4 — Application use cases

- [ ] [21 — Identity use cases (resolve provider identity)](21-identity-use-cases.md) `[MVP]`
- [ ] [22 — Project use cases (CRUD)](22-project-use-cases.md) `[MVP]`
- [ ] [23 — Task use cases (proposal, approved create, CRUD, status)](23-task-use-cases.md) `[MVP]`
- [ ] [24 — Attachment use cases (register, link, authorize, presign)](24-attachment-use-cases.md) `[MVP]`
- [ ] [25 — Conversation workflow use cases (state + proposals)](25-conversation-use-cases.md) `[MVP]`

## Phase 5 — Agent layer

- [ ] [26 — Agent contract & command-based registry](26-agent-contract-and-registry.md) `[MVP]`
- [ ] [27 — Task-management LangGraph workflow](27-task-management-langgraph-workflow.md) `[MVP]`
- [ ] [28 — Agent tool adapters (project/task/attachment/identity)](28-agent-tool-adapters.md) `[MVP]`
- [ ] [29 — Graph limits & retry bounds](29-graph-limits-and-retry.md) `[MVP]`

## Phase 6 — Channel adapters

- [ ] [30 — Normalized message contracts (inbound/outbound)](30-normalized-message-contracts.md) `[MVP]`
- [ ] [31 — Telegram adapter (long polling, text, images, delivery)](31-telegram-adapter.md) `[MVP]`
- [ ] [32 — Discord adapter boundary](32-discord-adapter-boundary.md) `[SEC]`

## Phase 7 — Bootstrap

- [ ] [33 — Composition root, startup & graceful shutdown](33-composition-root-and-startup.md) `[MVP]`

## Phase 8 — Correctness & safety (MVP-critical)

- [ ] [34 — Idempotency: provider events & business operations](34-idempotency.md) `[MVP]`
- [ ] [35 — Multi-user authorization & data isolation](35-multi-user-authorization.md) `[MVP]`

## Phase 9 — Testing

- [ ] [36 — Test fakes & harness (in-memory repos, fake model)](36-test-fakes-and-harness.md) `[MVP]`
- [ ] [37 — Unit tests (domain, application, agent)](37-unit-tests.md) `[MVP]`
- [ ] [38 — Contract tests (adapter contracts)](38-contract-tests.md) `[MVP]`
- [ ] [39 — Integration & end-to-end tests](39-integration-and-e2e-tests.md) `[MVP]`
- [ ] [40 — Security isolation tests](40-security-isolation-tests.md) `[MVP]`

## Phase 10 — Ops & hardening

- [ ] [41 — Attachment cleanup worker](41-attachment-cleanup-worker.md) `[MVP]`
- [ ] [42 — Observability: logging, metrics, correlation](42-observability.md) `[MVP]`
- [ ] [43 — Error handling & recovery](43-error-handling-and-recovery.md) `[MVP]`

## How to use

1. Work top to bottom; earlier phases unblock later ones.
2. Task 04 (open decisions) must close before 15 (migrations) and any adapter contract are finalized.
3. Keep changes small and focused; one task = one PR-sized chunk.
4. Label technical claims `[CODE]` / `[UNTESTED]` / `[VERIFIED]`.
