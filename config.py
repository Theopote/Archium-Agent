"""
Backward-compatible configuration shim for Archium v0.1 modules.

New code should use ``archium.config.get_settings()`` and
``archium.infrastructure.llm.get_llm_provider()`` directly.
Importing this module no longer requires an API key.
"""

from __future__ import annotations

from typing import Any

from archium.config.settings import get_settings
from archium.exceptions import ConfigurationError
from openai import OpenAI

_settings = get_settings()

GEMINI_API_KEY: str | None = _settings.llm_api_key
GEMINI_BASE_URL: str = _settings.llm_base_url or (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)
GEMINI_MODEL: str = _settings.llm_model

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Return a lazily initialized OpenAI-compatible client."""
    global _client
    if _client is None:
        if not _settings.llm_api_key:
            raise ConfigurationError(
                "未配置 LLM API Key。请在 .env 中设置 GEMINI_API_KEY 或 LLM_API_KEY。"
            )
        _client = OpenAI(
            api_key=_settings.llm_api_key,
            base_url=_settings.llm_base_url,
            timeout=_settings.llm_timeout_seconds,
        )
    return _client


class _ClientProxy:
    """Lazy proxy so legacy ``from config import client`` keeps working."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_client(), name)


client = _ClientProxy()
