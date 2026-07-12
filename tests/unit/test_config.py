"""Unit tests for the shared config loader (task 03)."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from mango_agent.shared.infrastructure.config import AppConfig, ConfigError, load_config
from mango_agent.shared.infrastructure.secrets import REDACTED, redact

ENV_VARS = [
    "CHANNEL",
    "BOT_INSTANCE",
    "AGENT_COMMAND",
    "DATABASE_URL",
    "REDIS_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_TOKEN",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENABLED",
    "LANGSMITH_PROJECT",
    "ENV",
    "LOG_LEVEL",
    "REDACT_SECRETS",
]


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _set_required(monkeypatch: pytest.MonkeyPatch, *, channel: str = "telegram") -> None:
    monkeypatch.setenv("CHANNEL", channel)
    monkeypatch.setenv("BOT_INSTANCE", "task-telegram")
    monkeypatch.setenv("AGENT_COMMAND", "task_management")
    monkeypatch.setenv("DATABASE_URL", "postgresql://mango:mango@localhost:5432/mango")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    if channel == "telegram":
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    else:
        monkeypatch.setenv("DISCORD_TOKEN", "tok")


def test_missing_required_raises_config_error(clean_env: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    message = str(excinfo.value)
    assert "bot_instance" in message
    assert "agent_command" in message
    assert "channel" in message
    assert "database_url" in message
    assert "redis_url" in message
    assert "anthropic_api_key" in message
    assert "anthropic_model" in message


def test_invalid_channel_raises_config_error(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("CHANNEL", "bogus")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "channel" in str(excinfo.value)


def test_empty_required_string_fails_fast(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("BOT_INSTANCE", "")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "BOT_INSTANCE" in str(excinfo.value)


def test_missing_channel_token_fails(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)


def test_discord_channel_uses_discord_token(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_required(monkeypatch, channel="discord")
    config = load_config()
    assert config.channel.channel == "discord"
    assert config.channel.discord_token is not None
    assert config.channel.discord_token.get_secret_value() == "tok"


def test_valid_config_loads(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.instance.bot_instance == "task-telegram"
    assert config.channel.channel == "telegram"
    assert config.channel.telegram_bot_token is not None
    assert config.channel.telegram_bot_token.get_secret_value() == "tok"
    assert config.model.anthropic_model == "claude-test"
    assert config.logging.env == "dev"
    assert config.langsmith.langsmith_enabled is False


def test_r2_all_or_nothing_fails(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("R2_BUCKET", "mango-attachments")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "R2" in str(excinfo.value)


def test_r2_complete_is_valid(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "keyid")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "mango-attachments")
    config = load_config()
    assert config.r2.r2_bucket == "mango-attachments"


def test_langsmith_enabled_requires_key(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("LANGSMITH_ENABLED", "true")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "LANGSMITH_API_KEY" in str(excinfo.value)


def test_langsmith_enabled_with_key_is_valid(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")
    config = load_config()
    assert config.langsmith.langsmith_enabled is True


def test_secrets_redacted_in_repr(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-secret-abcdef")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-ghijkl")
    config = load_config()
    rendered = repr(config)
    assert "tg-secret-abcdef" not in rendered
    assert "sk-secret-ghijkl" not in rendered


def test_redact_masks_secret_values() -> None:
    values = {"token": SecretStr("secret-value"), "level": "INFO"}
    masked = redact(values)
    assert masked == {"token": REDACTED, "level": "INFO"}


def test_dotenv_file_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHANNEL=telegram\n"
        "BOT_INSTANCE=task-telegram\n"
        "AGENT_COMMAND=task_management\n"
        "DATABASE_URL=postgresql://mango:mango@localhost:5432/mango\n"
        "REDIS_URL=redis://localhost:6379/0\n"
        "ANTHROPIC_API_KEY=sk-test\n"
        "ANTHROPIC_MODEL=claude-test\n"
        "TELEGRAM_BOT_TOKEN=tok\n"
    )
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.instance.bot_instance == "task-telegram"
    assert config.channel.telegram_bot_token is not None
    assert config.channel.telegram_bot_token.get_secret_value() == "tok"
