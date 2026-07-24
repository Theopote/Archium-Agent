"""LLM infrastructure."""

from typing import TYPE_CHECKING, Any

from archium.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse
from archium.infrastructure.llm.factory import (
    create_llm_provider,
    get_llm_provider,
    reset_llm_provider_cache,
)
from archium.infrastructure.llm.mock import MockLLMProvider

if TYPE_CHECKING:
    from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "create_llm_provider",
    "get_llm_provider",
    "reset_llm_provider_cache",
]


def __getattr__(name: str) -> Any:
    if name == "OpenAICompatibleProvider":
        from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
