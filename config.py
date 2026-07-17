"""
Backward-compatible configuration shim for Archium v0.1 modules.

New code should use ``archium.config.get_settings()`` directly.
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

ARCHIUM_IDENTITY = """\
你是 Archium（阿基姆），一位资深的架构与知识管理智能体——名字寓意 Architecture（建筑）与 Museum（博物馆）的结合，既关注空间与结构的秩序，也重视知识的归档与呈现。
你的语气像一位专业、冷静、高效的建筑师助理：表述精准、条理分明、直奔要点，不使用浮夸或多余的寒暄。
"""

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
        )
    return _client


class _ClientProxy:
    """Lazy proxy so legacy ``from config import client`` keeps working."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_client(), name)


client = _ClientProxy()
