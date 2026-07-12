---
phase: 0
order: "02"
mvp: true
title: Docker Compose local dev (Postgres + Redis)
refs:
  - PRD §16.4, §17.1
  - SDD §7
---

# 02 — Docker Compose local dev (Postgres + Redis)

Goal: Local `docker compose` with shared Postgres + Redis and one reusable `mango-app` image; one service per configured bot instance.

## Checklist

- [ ] Write `docker/Dockerfile` building the single reusable image from the monorepo.
- [ ] Write `docker-compose.yml` with `postgres` and `redis` services (volumes, healthchecks).
- [ ] Add a `mango-task-telegram` service using the image with `CHANNEL=telegram`, `BOT_INSTANCE=task-telegram`, `AGENT_COMMAND=task_management`.
- [ ] Parameterize via env: channel creds, agent command, model, PG/Redis/R2, LangSmith.
- [ ] Add a separate migration/worker service note (migrations must NOT run in every bot container).
- [ ] Postgres healthcheck + Redis healthcheck; bot waits for healthy before polling.
- [ ] `docker compose up` brings PG + Redis healthy; bot service starts and exits clean on missing config.
- [ ] Document local bring-up in `README.md`.
