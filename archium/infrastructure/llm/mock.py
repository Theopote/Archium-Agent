"""Mock LLM provider for tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from archium.infrastructure.llm.base import LLMRequest
from archium.infrastructure.llm.structured import parse_and_validate

T = TypeVar("T", bound=BaseModel)

ResponseSelector = Callable[[LLMRequest], str | None]


class MockLLMProvider:
    """Deterministic LLM provider for unit and integration tests."""

    def __init__(
        self,
        *,
        default_text: str = "mock response",
        text_responses: dict[str, str] | None = None,
        selector: ResponseSelector | None = None,
    ) -> None:
        self.default_text = default_text
        self.text_responses = text_responses or {}
        self.selector = selector
        self.calls: list[LLMRequest] = []

    def generate_text(self, request: LLMRequest) -> str:
        self.calls.append(request)
        return self._resolve(request)

    def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        self.calls.append(request)
        raw = self._resolve(request)
        return parse_and_validate(raw, schema)

    def _resolve(self, request: LLMRequest) -> str:
        if self.selector is not None:
            selected = self.selector(request)
            if selected is not None:
                return selected

        for key, value in self.text_responses.items():
            if key in request.user_prompt or key in request.system_prompt:
                return value

        return self.default_text
