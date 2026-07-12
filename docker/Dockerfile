# syntax=docker/dockerfile:1

# ---- Builder: install dependencies with uv ----
FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN pip install --no-cache-dir uv==0.11.16

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

# Copy application source and install the project (creates the mango-agent script).
COPY README.md ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# ---- Runtime: slim image with the venv and app ----
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system --gid 10001 mango \
    && useradd --system --uid 10001 --gid mango --create-home --home-dir /home/mango mango

WORKDIR /app
COPY --from=builder --chown=mango:mango /app/.venv /app/.venv
COPY --from=builder --chown=mango:mango /app/src /app/src
COPY --from=builder --chown=mango:mango /app/pyproject.toml /app/pyproject.toml

USER mango
CMD ["mango-agent"]
