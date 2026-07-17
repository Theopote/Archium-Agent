"""Cached LLM response selector for fixture acceptance tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from archium.infrastructure.llm import LLMRequest
from tests.fixtures.mock_llm import pipeline_mock_selector

_CACHE_DIR = Path(__file__).resolve().parent / "llm_cache"


def load_cached_llm_selector(case_id: str) -> Callable[[LLMRequest], str | None]:
    """Return a selector that prefers cached responses, then falls back to pipeline mock."""
    cache_path = _CACHE_DIR / f"{case_id}.json"
    if not cache_path.exists():
        return pipeline_mock_selector

    entries: dict[str, str] = json.loads(cache_path.read_text(encoding="utf-8"))

    def selector(request: LLMRequest) -> str | None:
        haystack = f"{request.system_prompt}\n{request.user_prompt}"
        for needle, response in entries.items():
            if needle in haystack:
                return response
        return pipeline_mock_selector(request)

    return selector
