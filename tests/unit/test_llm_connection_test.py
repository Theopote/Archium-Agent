"""Unit tests for LLM connection test helper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError, RateLimitError

from archium.infrastructure.llm.connection_test import verify_llm_connection


def _mock_client(*, content: str = "ARCHIUM_CONNECTION_OK", side_effect: Exception | None = None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.chat.completions.create.side_effect = side_effect
    else:
        choice = MagicMock()
        choice.message.content = content
        response = MagicMock()
        response.choices = [choice]
        client.chat.completions.create.return_value = response
    return client


def test_connection_success() -> None:
    result = verify_llm_connection(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="test-model",
        client=_mock_client(),
    )
    assert result.success is True
    assert result.model == "test-model"
    assert result.latency_ms >= 0


def test_connection_authentication_error() -> None:
    result = verify_llm_connection(
        api_key="bad-key",
        base_url="https://example.test/v1/",
        model="test-model",
        client=_mock_client(side_effect=AuthenticationError("invalid", response=MagicMock(), body=None)),
    )
    assert result.success is False
    assert result.error_code == "authentication_failed"
    assert "API Key" in result.message


def test_connection_rate_limit_error() -> None:
    result = verify_llm_connection(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="test-model",
        client=_mock_client(side_effect=RateLimitError("limited", response=MagicMock(), body=None)),
    )
    assert result.success is False
    assert result.error_code == "rate_limited"


def test_connection_generic_error_is_sanitized() -> None:
    result = verify_llm_connection(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="test-model",
        client=_mock_client(side_effect=RuntimeError("secret header sk-abc")),
    )
    assert result.success is False
    assert "sk-abc" not in result.message
