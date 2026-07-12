# Mango Agent

Multi-user personal AI agent for managing projects and tasks via natural-language conversations. Telegram-first, Discord-secondary. Python modular monolith, Hexagonal Architecture.

## Local development

### Prerequisites

- [Docker](https://www.docker.com/) with the Compose plugin (for Postgres + Redis + the app image)
- [uv](https://docs.astral.sh/uv/) (for local Python tooling)

### Quickstart with Docker Compose

```bash
cp .env.example .env
docker compose up -d postgres redis
docker compose up mango-task-telegram
```

With `.env` populated, `mango-task-telegram` prints its instance identity and exits cleanly (the Telegram polling loop arrives in task 31). Postgres and Redis stay healthy in the background.

### Fail-fast behavior

The bot validates required env at startup. Without the identity vars it exits non-zero with an actionable message:

```bash
docker compose up mango-task-telegram   # no .env -> exits 1: "missing required env: CHANNEL, BOT_INSTANCE, ..."
```

`docker compose up -d postgres redis` brings up only the infrastructure (no bot).

### Migrations (placeholder)

Migrations run in a dedicated one-shot service, never inside every bot container:

```bash
docker compose --profile migrate run --rm mango-migrate
```

The actual migration tooling and schema land in task 15; until then this prints a not-implemented notice and exits 0.

### Infrastructure

| Service | Image | Host port | Healthcheck |
| --- | --- | --- | --- |
| `postgres` | `postgres:17-alpine` | `5432` | `pg_isready` |
| `redis` | `redis:7-alpine` | `6379` | `redis-cli ping` |

Postgres data is persisted in the `mango_pgdata` volume; Redis state is ephemeral. Cloudflare R2 and the Anthropic model provider remain external managed services, configured via env.

### Local Python tooling

```bash
uv sync                 # install dev dependencies
uv run pytest           # tests (includes the import-linter dependency-rule guard)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # strict type check on src/mango_agent
uv run pre-commit run --all-files
```

### Configuration

See `.env.example` for all environment variables. Task 03 introduces the full typed, validated config object; secrets are sourced only from env/deployment config and are never logged or committed.
