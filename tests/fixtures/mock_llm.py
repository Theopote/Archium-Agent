"""Shared mock LLM selector for presentation pipeline and workflow tests."""

from __future__ import annotations

from archium.infrastructure.llm import LLMRequest

from tests.fixtures.mock_presentation_responses import (
    BRIEF_JSON,
    SLIDE_PLAN_JSON,
    STORYLINE_JSON,
)


def pipeline_mock_selector(request: LLMRequest) -> str | None:
    user_prompt = request.user_prompt
    if "生成 PresentationBrief JSON" in user_prompt:
        return BRIEF_JSON
    if "生成 Storyline JSON" in user_prompt:
        return STORYLINE_JSON
    if "SlidePlan JSON" in user_prompt:
        return SLIDE_PLAN_JSON
    return None
