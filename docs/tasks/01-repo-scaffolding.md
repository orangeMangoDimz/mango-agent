---
phase: 0
order: "01"
mvp: true
title: Repo scaffolding, tooling & folder structure
refs:
  - PRD §17.1, §20
  - SDD §27
  - AGENTS.md (Repo layout)
---

# 01 — Repo scaffolding, tooling & folder structure

Goal: Stand up the `src/mango_agent/` Hexagonal skeleton from PRD §20 with `uv`, lint/format, and pytest configured.

## Checklist

- [ ] Confirm `uv` project init; set package layout (`src/`).
- [ ] Create `src/mango_agent/` root package with `__init__.py`.
- [ ] Create `bootstrap/`, `channels/{telegram,discord}/`, `agents/task_management/`.
- [ ] Create `modules/{identity,task_management,attachments,conversation}/` each with `domain/ application/ ports/ adapters/`.
- [ ] Create `integrations/llm/` and `shared/{domain,infrastructure}/`.
- [ ] Create top-level `migrations/`, `tests/{unit,integration,contract,end_to_end,fakes}/`, `scripts/`, `docker/`.
- [ ] Add `ruff` (lint + format) and `pytest` dev dependencies.
- [ ] Add `pyproject.toml` tool config: ruff rules, pytest paths, mypy (optional).
- [ ] Add `.env.example` placeholder and extend `.gitignore` (`.env`, `*.log`, `.ruff_cache`).
- [ ] Add `pre-commit` hooks (ruff, format) — optional.
- [ ] Add dependency-rule guard: a test/script asserting inner layers don't import infra SDKs.
- [ ] `uv sync` + `uv run pytest` green on an empty test.
