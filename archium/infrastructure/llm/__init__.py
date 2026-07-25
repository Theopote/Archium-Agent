"""LLM infrastructure."""

from typing import TYPE_CHECKING, Any

from archium.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.factory import (
    create_llm_provider,
    get_llm_provider,
    reset_llm_provider_cache,
)
from archium.infrastructure.llm.mock import MockLLMProvider
from archium.infrastructure.llm.runtime import LLMRuntime
from archium.infrastructure.llm.trace import (
    LLMTrace,
    get_llm_trace_recorder,
    set_llm_trace_recorder,
)

if TYPE_CHECKING:
    from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "LLMCapability",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMRuntime",
    "LLMTrace",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "create_llm_provider",
    "get_llm_provider",
    "get_llm_trace_recorder",
    "reset_llm_provider_cache",
    "set_llm_trace_recorder",
]


def __getattr__(name: str) -> Any:
    if name == "OpenAICompatibleProvider":
        from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
