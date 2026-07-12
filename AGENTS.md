# Mango Agent — Project Instructions

Mango Agent is a multi-user personal AI agent for managing projects and tasks via natural-language conversations. Python modular monolith, Hexagonal Architecture (Ports & Adapters). Telegram primary, Discord secondary. Anthropic + LangChain/LangGraph/LangSmith. PostgreSQL, Redis, Cloudflare R2. Docker Compose. Dependency management: `uv`.

## Source of truth (read before implementing)

- `docs/PRD.md` — Product Requirements Document v1.0.0
- `docs/SYSTEM_DESIGN.md` — System Design Document v0.3.0

These are snapshots from Notion (see each file's front matter for source URL + fetch date). Treat them as authoritative for scope, contracts, and invariants. Re-fetch from Notion if they may be stale.

## Subagent routing

Delegate domain work to the project subagents in `.cursor/agents/`:

- `channel-agent` — platform/channel layer: Telegram/Discord adapters, normalized inbound/outbound message contracts, provider identity mapping, message formatting and delivery.
- `mango-agent` — core orchestration: agent router/registry, LangGraph workflows, tools, (future) MCP, conversation memory/state, human-in-the-loop proposal/approval flow.
- `database-agent` — data layer: PostgreSQL schema/tables/queries/migrations, repository contracts, Redis state, R2 attachment metadata, idempotency records.

## Non-negotiable invariants

- Every operation is scoped to an authenticated internal user; user scope is never inferred from model output.
- Human approval required before task creation; confirmation before deletion; confirm sensitive updates.
- Agents never touch infrastructure directly — they call application use cases through tools.
- No raw image bytes or temporary presigned URLs in PostgreSQL; only metadata + the stable R2 object key.
- Idempotency for provider events and for approvals/business operations — no duplicate records.
- Dependency direction: Channels → Agents → Application → Domain/Ports ← Adapters. Inner layers must not import Telegram/Discord/Postgres/Redis/R2/Anthropic/LangSmith.
- Routing is a deterministic command registry (e.g. `task_management`), never LLM intent classification.

## Repo layout (target)

See `docs/PRD.md` §20 for the full `src/mango_agent/` Hexagonal folder structure: `bootstrap/`, `channels/{telegram,discord}/`, `agents/task_management/`, `modules/{identity,task_management,attachments,conversation}/` (each with `domain/application/ports/adapters/`), `integrations/llm/`, `shared/`, plus top-level `migrations/`, `tests/{unit,integration,contract,end_to_end,fakes}/`, `scripts/`, `docker/`.

Each business module follows: `domain → application → ports ← adapters`.

## Conventions

- Favor immutable data, early returns, named constants, small focused units.
- Label technical claims with evidence: `[CODE]` / `[UNTESTED]` / `[VERIFIED]`.
- Don't invent APIs, file paths, or runtime behavior — verify with tools or say it's unknown.
- Keep changes small and focused; no broad refactors unless asked.
