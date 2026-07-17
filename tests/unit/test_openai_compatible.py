"""Tests for OpenAICompatibleProvider with mocked client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from archium.config.settings import Settings
from archium.infrastructure.llm.base import LLMRequest
from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider
from archium.infrastructure.llm.schemas import RouterPlan


def _mock_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    response = MagicMock()
    response.model = "test-model"
    response.choices = [choice]
    return response


def test_openai_provider_generate_text() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("hello world")
    settings = Settings(_env_file=None, llm_api_key="test-key", llm_model="test-model")
    provider = OpenAICompatibleProvider(settings, client=client)

    result = provider.generate_text(
        LLMRequest(system_prompt="sys", user_prompt="user"),
    )
    assert result == "hello world"
    client.chat.completions.create.assert_called_once()


def test_openai_provider_generate_structured() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(
        '{"summary": "ok", "steps": []}'
    )
    settings = Settings(_env_file=None, llm_api_key="test-key", llm_model="test-model")
    provider = OpenAICompatibleProvider(settings, client=client)

    plan = provider.generate_structured(
        LLMRequest(system_prompt="sys", user_prompt="user"),
        RouterPlan,
    )
    assert plan.summary == "ok"
    assert plan.steps == []


def test_openai_provider_retries_transient_errors() -> None:
    from openai import APIConnectionError

    client = MagicMock()
    request = MagicMock()
    client.chat.completions.create.side_effect = [
        APIConnectionError(request=request),
        _mock_completion("recovered"),
    ]
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_model="test-model",
        llm_max_retries=1,
    )
    provider = OpenAICompatibleProvider(settings, client=client)

    with patch("archium.infrastructure.llm.openai_compatible.time.sleep"):
        result = provider.generate_text(
            LLMRequest(system_prompt="sys", user_prompt="user"),
        )
    assert result == "recovered"
    assert client.chat.completions.create.call_count == 2
