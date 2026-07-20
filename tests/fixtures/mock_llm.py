"""Shared mock LLM selector for presentation pipeline and workflow tests."""

from __future__ import annotations

import re

from archium.infrastructure.llm import LLMRequest

from tests.fixtures.mock_full_deck_responses import (
    FULL_DECK_BRIEF_JSON,
    FULL_DECK_SLIDE_PLAN_JSON,
    FULL_DECK_STORYLINE_JSON,
)
from tests.fixtures.mock_presentation_responses import (
    BRIEF_ALIGNMENT_MISMATCH_JSON,
    BRIEF_ALIGNMENT_OK_JSON,
    BRIEF_JSON,
    FACT_EXTRACTION_JSON,
    LAYER_REVIEW_JSON,
    PROFESSIONAL_REVIEW_JSON,
    SLIDE_PLAN_JSON,
    SLIDE_REPAIR_JSON,
    SLIDE_SPLIT_JSON,
    STORYLINE_JSON,
    CULTURAL_NARRATIVE_JSON,
)


def _wants_full_deck(request: LLMRequest) -> bool:
    haystack = request.user_prompt
    if "目标页数: 20" in haystack or "请生成约 20 页" in haystack:
        return True
    match = re.search(r'"target_slide_count"\s*:\s*(\d+)', haystack)
    if match and int(match.group(1)) >= 15:
        return True
    match = re.search(r"target_slide_count[=:\s]+(\d+)", haystack)
    return bool(match and int(match.group(1)) >= 15)


def pipeline_mock_selector(request: LLMRequest) -> str | None:
    user_prompt = request.user_prompt
    full_deck = _wants_full_deck(request)
    if "生成 PresentationBrief JSON" in user_prompt:
        return FULL_DECK_BRIEF_JSON if full_deck else BRIEF_JSON
    if "生成 Storyline JSON" in user_prompt:
        return FULL_DECK_STORYLINE_JSON if full_deck else STORYLINE_JSON
    if "CulturalNarrativePlan JSON" in user_prompt:
        return CULTURAL_NARRATIVE_JSON
    if "SlidePlan JSON" in user_prompt:
        return FULL_DECK_SLIDE_PLAN_JSON if full_deck else SLIDE_PLAN_JSON
    if (
        "FactExtraction" in user_prompt
        or "ProjectFact JSON" in user_prompt
        or "结构化事实 JSON" in user_prompt
        or "ProjectFact" in request.system_prompt
    ):
        return FACT_EXTRACTION_JSON
    if "BriefAlignment JSON" in user_prompt:
        return BRIEF_ALIGNMENT_MISMATCH_JSON
    if "ProfessionalReview JSON" in user_prompt:
        return LAYER_REVIEW_JSON
    if "ProfessionalReview" in user_prompt:
        return PROFESSIONAL_REVIEW_JSON
    if "修订以下页面 JSON" in user_prompt:
        return SLIDE_REPAIR_JSON
    if "叙事合理的两页拆分方案" in user_prompt:
        return SLIDE_SPLIT_JSON
    return None


def brief_alignment_ok_selector(request: LLMRequest) -> str | None:
    if "BriefAlignment JSON" in request.user_prompt:
        return BRIEF_ALIGNMENT_OK_JSON
    return pipeline_mock_selector(request)
