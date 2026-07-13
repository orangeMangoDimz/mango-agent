"""Composition-root tests for LangChain model initialization."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

import mango_agent.bootstrap.container as container_module
from mango_agent.integrations.llm.langchain_model import LangChainModelPort
from mango_agent.shared.infrastructure.config import ConfigError


def _config() -> Any:
    return SimpleNamespace(
        model=SimpleNamespace(
            model_name="anthropic:claude-test",
            anthropic_api_key=SecretStr("sk-secret"),
        )
    )


def test_model_port_uses_langchain_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = FakeMessagesListChatModel(responses=[AIMessage(content="ok")])
    captured: dict[str, object] = {}

    def fake_init_chat_model(model: str, **kwargs: object) -> FakeMessagesListChatModel:
        captured.update(model=model, **kwargs)
        return fake_model

    monkeypatch.setattr(container_module, "init_chat_model", fake_init_chat_model)

    port = container_module._model_port(_config())

    assert isinstance(port, LangChainModelPort)
    assert captured == {
        "model": "anthropic:claude-test",
        "api_key": "sk-secret",
        "max_tokens": 1024,
    }


def test_model_initialization_failure_is_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_init_chat_model(model: str, **kwargs: object) -> None:
        raise ImportError(f"cannot initialize {model} with {kwargs['api_key']}")

    monkeypatch.setattr(container_module, "init_chat_model", fail_init_chat_model)

    with pytest.raises(ConfigError) as excinfo:
        container_module._model_port(_config())

    message = str(excinfo.value)
    assert "MODEL_NAME" in message
    assert "sk-secret" not in message
