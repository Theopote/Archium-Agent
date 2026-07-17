"""LLM request/response types and provider protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMRequest:
    """Input for a single LLM call."""

    system_prompt: str
    user_prompt: str
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    json_mode: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Raw LLM response wrapper."""

    content: str
    model: str
    finish_reason: str | None = None


class LLMProvider(Protocol):
    """Abstract LLM provider interface."""

    def generate_text(self, request: LLMRequest) -> str:
        """Generate free-form text."""
        ...

    def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        """Generate and validate structured output against a Pydantic schema."""
        ...
