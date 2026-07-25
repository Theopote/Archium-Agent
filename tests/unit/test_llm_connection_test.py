"""Unit tests for LLM connection test helper."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.infrastructure.llm.connection_test import (
    normalize_api_key,
    verify_llm_connection,
)
from openai import AuthenticationError, BadRequestError, NotFoundError, RateLimitError


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


def test_gemini_style_bad_request_maps_to_authentication() -> None:
    """Gemini OpenAI-compat returns 400 INVALID_ARGUMENT for bad keys, not 401."""
    response = MagicMock()
    response.status_code = 400
    response.headers = {}
    result = verify_llm_connection(
        api_key="AIzaSyFAKE",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        client=_mock_client(
            side_effect=BadRequestError(
                "Error code: 400",
                response=response,
                body={
                    "error": {
                        "code": 400,
                        "message": "Please pass a valid API key",
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )
        ),
    )
    assert result.success is False
    assert result.error_code == "authentication_failed"
    assert result.detail is not None
    assert "valid API key" in result.detail


def test_not_found_maps_to_model_error() -> None:
    response = MagicMock()
    response.status_code = 404
    response.headers = {}
    result = verify_llm_connection(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="missing-model",
        client=_mock_client(
            side_effect=NotFoundError(
                "not found",
                response=response,
                body={"error": {"message": "model not found"}},
            )
        ),
    )
    assert result.success is False
    assert result.error_code == "model_not_found"
    assert "missing-model" in result.message


def test_connection_generic_error_is_sanitized() -> None:
    result = verify_llm_connection(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="test-model",
        client=_mock_client(side_effect=RuntimeError("secret header sk-abc123456789")),
    )
    assert result.success is False
    assert "sk-abc123456789" not in (result.message or "")
    assert "sk-abc123456789" not in (result.detail or "")
    assert "***" in (result.detail or "")


def test_normalize_api_key_strips_quotes_and_bom() -> None:
    assert normalize_api_key('  "AIzaSyTest"  ') == "AIzaSyTest"
    assert normalize_api_key("\ufeffAIzaSyTest") == "AIzaSyTest"
