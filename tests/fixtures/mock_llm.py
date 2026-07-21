"""Shared mock LLM selector for presentation pipeline and workflow tests."""

from __future__ import annotations

import json
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
    CULTURAL_NARRATIVE_JSON,
    FACT_EXTRACTION_JSON,
    LAYER_REVIEW_JSON,
    PROFESSIONAL_REVIEW_JSON,
    REFERENCE_STYLE_PROFILE_JSON,
    RENOVATION_ISSUE_MAP_JSON,
    SLIDE_PLAN_JSON,
    SLIDE_REPAIR_JSON,
    SLIDE_SPLIT_JSON,
    STORYLINE_JSON,
)


def _wants_full_deck(request: LLMRequest) -> bool:
    haystack = request.user_prompt
    match = re.search(r"目标页数:\s*(\d+)", haystack)
    if match and int(match.group(1)) >= 15:
        return True
    match = re.search(r"请生成约\s*(\d+)\s*页", haystack)
    if match and int(match.group(1)) >= 15:
        return True
    match = re.search(r'"target_slide_count"\s*:\s*(\d+)', haystack)
    if match and int(match.group(1)) >= 15:
        return True
    match = re.search(r"target_slide_count[=:\s]+(\d+)", haystack)
    return bool(match and int(match.group(1)) >= 15)


def _single_slide_plan_response(request: LLMRequest, *, full_deck: bool) -> str | None:
    if "生成单页 SlideSpec JSON" not in request.user_prompt:
        return None
    plan_source = FULL_DECK_SLIDE_PLAN_JSON if full_deck else SLIDE_PLAN_JSON
    plan = json.loads(plan_source)
    order_match = re.search(r"页序：(\d+)", request.user_prompt)
    chapter_match = re.search(r"章节：([^，]+)", request.user_prompt)
    if order_match is None:
        return None
    order = int(order_match.group(1))
    chapter_id = chapter_match.group(1).strip() if chapter_match else "ch1"
    for slide in plan.get("slides", []):
        if int(slide.get("order", -1)) == order:
            payload = dict(slide)
            payload["chapter_id"] = chapter_id
            payload["order"] = order
            return json.dumps(payload, ensure_ascii=False)
    slides = plan.get("slides", [])
    if slides:
        template = dict(slides[min(order, len(slides) - 1)])
        template["chapter_id"] = chapter_id
        template["order"] = order
        template["title"] = f"{template.get('title', '页面')} {order + 1}"
        return json.dumps(template, ensure_ascii=False)
    return json.dumps(
        {
            "chapter_id": chapter_id,
            "order": order,
            "title": f"页面 {order + 1}",
            "message": "待补充核心观点",
            "slide_type": "content",
            "layout_id": "default",
            "key_points": [],
            "visual_requirements": [],
            "source_citations": [],
            "speaker_notes": None,
        },
        ensure_ascii=False,
    )


def pipeline_mock_selector(request: LLMRequest) -> str | None:
    user_prompt = request.user_prompt
    full_deck = _wants_full_deck(request)
    single_slide = _single_slide_plan_response(request, full_deck=full_deck)
    if single_slide is not None:
        return single_slide
    if "生成 PresentationBrief JSON" in user_prompt:
        return FULL_DECK_BRIEF_JSON if full_deck else BRIEF_JSON
    if "生成 Storyline JSON" in user_prompt:
        return FULL_DECK_STORYLINE_JSON if full_deck else STORYLINE_JSON
    if "CulturalNarrativePlan JSON" in user_prompt:
        return CULTURAL_NARRATIVE_JSON
    if "RenovationIssueMap JSON" in user_prompt:
        return RENOVATION_ISSUE_MAP_JSON
    if "ReferenceStyleProfile JSON" in user_prompt:
        return REFERENCE_STYLE_PROFILE_JSON
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
