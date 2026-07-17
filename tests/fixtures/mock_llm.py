"""Shared mock LLM selector for presentation pipeline and workflow tests."""

from __future__ import annotations

from archium.infrastructure.llm import LLMRequest

from tests.fixtures.mock_presentation_responses import (
    BRIEF_ALIGNMENT_MISMATCH_JSON,
    BRIEF_ALIGNMENT_OK_JSON,
    BRIEF_JSON,
    FACT_EXTRACTION_JSON,
    LAYER_REVIEW_JSON,
    PROFESSIONAL_REVIEW_JSON,
    SLIDE_PLAN_JSON,
    SLIDE_REPAIR_JSON,
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
    if "FactExtraction" in user_prompt or "ProjectFact JSON" in user_prompt:
        return FACT_EXTRACTION_JSON
    if "BriefAlignment JSON" in user_prompt:
        return BRIEF_ALIGNMENT_MISMATCH_JSON
    if "ProfessionalReview JSON" in user_prompt:
        return LAYER_REVIEW_JSON
    if "ProfessionalReview" in user_prompt:
        return PROFESSIONAL_REVIEW_JSON
    if "修订以下页面 JSON" in user_prompt:
        return SLIDE_REPAIR_JSON
    return None


def brief_alignment_ok_selector(request: LLMRequest) -> str | None:
    if "BriefAlignment JSON" in request.user_prompt:
        return BRIEF_ALIGNMENT_OK_JSON
    return pipeline_mock_selector(request)
