"""Typed application configuration loaded from the environment with fail-fast validation.

Central ``AppConfig`` with nested groups, loaded once at startup by the
composition root (task 33). Secrets are stored as pydantic ``SecretStr`` and
redacted from logs via ``shared.infrastructure.secrets``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Raised when configuration is missing or invalid at startup."""


class _BaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class InstanceConfig(_BaseSettings):
    bot_instance: str
    agent_command: str


class ChannelConfig(_BaseSettings):
    channel: Literal["telegram", "discord"]
    telegram_bot_token: SecretStr | None = None
    discord_token: SecretStr | None = None


class ModelConfig(_BaseSettings):
    anthropic_api_key: SecretStr
    anthropic_model: str


class PostgresConfig(_BaseSettings):
    database_url: SecretStr


class RedisConfig(_BaseSettings):
    redis_url: SecretStr


class R2Config(_BaseSettings):
    r2_account_id: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = None


class LangSmithConfig(_BaseSettings):
    langsmith_api_key: SecretStr | None = None
    langsmith_enabled: bool = False
    langsmith_project: str | None = None


class AgentWorkflowConfig(_BaseSettings):
    """Bounded execution settings for the task-management workflow.

    The ``AGENT_`` prefix keeps these operational limits separate from model
    provider configuration while retaining normal 12-factor environment-based
    configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGENT_",
        extra="ignore",
        case_sensitive=False,
    )

    max_model_turns: int = Field(default=4, ge=1)
    max_tool_calls: int = Field(default=8, ge=1)
    max_invalid_tool_argument_repairs: int = Field(default=2, ge=1)


class LoggingConfig(_BaseSettings):
    log_level: str = "INFO"
    env: str = "dev"
    redact_secrets: bool = True


class AppConfig(BaseModel):
    instance: InstanceConfig
    channel: ChannelConfig
    model: ModelConfig
    postgres: PostgresConfig
    redis: RedisConfig
    r2: R2Config
    langsmith: LangSmithConfig
    agent_workflow: AgentWorkflowConfig
    logging: LoggingConfig


class WorkerConfig(BaseModel):
    """Configuration subset for background workers that do not need channel/model access."""

    instance: WorkerInstanceConfig
    postgres: PostgresConfig
    redis: RedisConfig
    r2: R2Config
    logging: LoggingConfig


class WorkerInstanceConfig(_BaseSettings):
    """Minimal instance identity for workers."""

    bot_instance: str


def _provided(value: str | SecretStr | None) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return value.get_secret_value() != ""
    return value != ""


def _try_build[T: BaseSettings](cls: type[T], errors: list[str]) -> T | None:
    try:
        return cls()
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            errors.append(f"  - {cls.__name__}.{loc}: {err['msg']}")
        return None


def _require_non_empty(errors: list[str], fields: Mapping[str, str | SecretStr | None]) -> None:
    for name, value in fields.items():
        if not _provided(value):
            errors.append(f"  - {name.upper()} must not be empty")


def load_config() -> AppConfig:
    errors: list[str] = []
    instance = _try_build(InstanceConfig, errors)
    channel = _try_build(ChannelConfig, errors)
    model = _try_build(ModelConfig, errors)
    postgres = _try_build(PostgresConfig, errors)
    redis = _try_build(RedisConfig, errors)
    r2 = _try_build(R2Config, errors)
    langsmith = _try_build(LangSmithConfig, errors)
    agent_workflow = _try_build(AgentWorkflowConfig, errors)
    logging_cfg = _try_build(LoggingConfig, errors)

    if instance is not None:
        _require_non_empty(
            errors,
            {"bot_instance": instance.bot_instance, "agent_command": instance.agent_command},
        )

    if channel is not None:
        if channel.channel == "telegram":
            token = channel.telegram_bot_token
            env_name = "TELEGRAM_BOT_TOKEN"
        else:
            token = channel.discord_token
            env_name = "DISCORD_TOKEN"
        if not _provided(token):
            errors.append(f"  - {env_name} is required for channel '{channel.channel}'")

    if model is not None:
        _require_non_empty(
            errors,
            {
                "anthropic_api_key": model.anthropic_api_key,
                "anthropic_model": model.anthropic_model,
            },
        )

    if postgres is not None:
        _require_non_empty(errors, {"database_url": postgres.database_url})

    if redis is not None:
        _require_non_empty(errors, {"redis_url": redis.redis_url})

    if r2 is not None:
        r2_fields = [
            _provided(r2.r2_account_id),
            _provided(r2.r2_access_key_id),
            _provided(r2.r2_secret_access_key),
            _provided(r2.r2_bucket),
        ]
        if 0 < sum(r2_fields) < len(r2_fields):
            errors.append(
                "  - R2 config is all-or-nothing: set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, and R2_BUCKET together"
            )

    if (
        langsmith is not None
        and langsmith.langsmith_enabled
        and not _provided(langsmith.langsmith_api_key)
    ):
        errors.append("  - LANGSMITH_API_KEY is required when LANGSMITH_ENABLED=true")

    if errors:
        raise ConfigError("configuration is missing or invalid:\n" + "\n".join(errors))

    assert instance is not None
    assert channel is not None
    assert model is not None
    assert postgres is not None
    assert redis is not None
    assert r2 is not None
    assert langsmith is not None
    assert agent_workflow is not None
    assert logging_cfg is not None

    return AppConfig(
        instance=instance,
        channel=channel,
        model=model,
        postgres=postgres,
        redis=redis,
        r2=r2,
        langsmith=langsmith,
        agent_workflow=agent_workflow,
        logging=logging_cfg,
    )


def load_worker_config() -> WorkerConfig:
    """Load the minimal configuration required by background workers."""
    errors: list[str] = []
    instance = _try_build(WorkerInstanceConfig, errors)
    postgres = _try_build(PostgresConfig, errors)
    redis = _try_build(RedisConfig, errors)
    r2 = _try_build(R2Config, errors)
    logging_cfg = _try_build(LoggingConfig, errors)

    if instance is not None:
        _require_non_empty(errors, {"bot_instance": instance.bot_instance})

    if postgres is not None:
        _require_non_empty(errors, {"database_url": postgres.database_url})

    if redis is not None:
        _require_non_empty(errors, {"redis_url": redis.redis_url})

    if r2 is not None:
        r2_fields = [
            _provided(r2.r2_account_id),
            _provided(r2.r2_access_key_id),
            _provided(r2.r2_secret_access_key),
            _provided(r2.r2_bucket),
        ]
        if 0 < sum(r2_fields) < len(r2_fields):
            errors.append(
                "  - R2 config is all-or-nothing: set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, and R2_BUCKET together"
            )

    if errors:
        raise ConfigError("worker configuration is missing or invalid:\n" + "\n".join(errors))

    assert instance is not None
    assert postgres is not None
    assert redis is not None
    assert r2 is not None
    assert logging_cfg is not None

    return WorkerConfig(
        instance=instance,
        postgres=postgres,
        redis=redis,
        r2=r2,
        logging=logging_cfg,
    )
