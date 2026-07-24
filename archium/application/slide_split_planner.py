"""Build narrative-aware slide split plans before execution."""

from __future__ import annotations

import re
from copy import deepcopy
from uuid import uuid4

from archium.application.slide_repair_policy import contains_protected_signal
from archium.application.slide_split_allocators import allocate_citations, allocate_visuals
from archium.application.slide_split_validator import validate_split_plan
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_split import GENERIC_CONTINUATION_MESSAGE, SlideSplitPlan
from archium.infrastructure.llm.base import LLMProvider

_STRATEGY_RE = re.compile(r"(?:策略|方案|措施|步骤|举措|路径)")
_PROBLEM_RE = re.compile(r"(?:问题|原因|现状|挑战|痛点|制约)")


def derive_continuation_title(original_title: str, moved_points: list[str]) -> str:
    moved_text = " ".join(moved_points)
    base = original_title.removesuffix("（续）").strip()
    if _STRATEGY_RE.search(moved_text):
        return f"{base} — 策略与措施"
    if _PROBLEM_RE.search(moved_text):
        return f"{base} — 问题与原因"
    if len(moved_points) == 1 and len(moved_points[0]) <= 30:
        return f"{base} — 补充说明"
    return f"{base}（续）"


def derive_continuation_message(moved_points: list[str]) -> str:
    if len(moved_points) == 1:
        return moved_points[0]
    moved_text = " ".join(moved_points)
    strategy_count = sum(1 for point in moved_points if _STRATEGY_RE.search(point))
    if strategy_count >= 2:
        return f"通过 {len(moved_points)} 项策略支撑上述改造方向。"
    problem_count = sum(1 for point in moved_points if _PROBLEM_RE.search(point))
    if problem_count >= 2:
        return "上述问题与原因需在本页一并说明。"
    if contains_protected_signal(moved_text):
        return moved_points[0]
    return GENERIC_CONTINUATION_MESSAGE


def build_split_plan(
    original: SlideSpec,
    updated_source: SlideSpec,
    moved_points: list[str],
    reason: str,
    *,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
    llm: LLMProvider | None = None,
    settings: Settings | None = None,
    brief: PresentationBrief | None = None,
) -> SlideSplitPlan:
    """Build a split plan; use LLM narrative planning when available."""
    rule_plan = _build_rule_split_plan(
        original,
        updated_source,
        moved_points,
        reason,
        storyline=storyline,
        chapter_slide_count=chapter_slide_count,
    )
    runtime_settings = settings or get_settings()
    if llm is None or not runtime_settings.slide_repair_enabled:
        return rule_plan

    from archium.application.slide_split_llm_planner import (
        choose_split_plan,
        try_build_llm_split_plan,
    )

    llm_plan = try_build_llm_split_plan(
        original,
        reason,
        llm=llm,
        settings=settings,
        brief=brief,
        storyline=storyline,
        chapter_slide_count=chapter_slide_count,
    )
    return choose_split_plan(rule_plan, llm_plan)


def _build_rule_split_plan(
    original: SlideSpec,
    updated_source: SlideSpec,
    moved_points: list[str],
    reason: str,
    *,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
) -> SlideSplitPlan:
    """Build a deterministic split plan with citation and asset remapping."""
    source = deepcopy(updated_source)
    order = source.order + 1
    continuation = SlideSpec(
        id=uuid4(),
        presentation_id=original.presentation_id,
        chapter_id=original.chapter_id,
        order=order,
        logical_key=build_slide_logical_key(original.chapter_id, order),
        title=derive_continuation_title(original.title, moved_points),
        message=derive_continuation_message(moved_points),
        slide_type=original.slide_type,
        layout_id=original.layout_id,
        key_points=list(moved_points),
        visual_requirements=[],
        source_citations=[],
        speaker_notes=None,
        status=original.status,
    )

    source_citations, continuation_citations, citation_mapping = allocate_citations(
        original,
        source,
        continuation,
        moved_points,
    )
    source_visuals, continuation_visuals, asset_mapping = allocate_visuals(
        original,
        source,
        continuation,
        moved_points,
    )

    source = source.model_copy(
        update={
            "source_citations": source_citations,
            "visual_requirements": source_visuals,
        }
    )
    continuation = continuation.model_copy(
        update={
            "source_citations": continuation_citations,
            "visual_requirements": continuation_visuals,
        }
    )

    plan = SlideSplitPlan(
        reason=reason,
        source_slide_id=original.id,
        new_slides=[source, continuation],
        citation_mapping=citation_mapping,
        asset_mapping=asset_mapping,
        planning_source="rule",
    )
    return validate_split_plan(
        plan,
        original=original,
        storyline=storyline,
        chapter_slide_count=chapter_slide_count,
    )


def build_split_slide(original: SlideSpec, moved_points: list[str]) -> SlideSpec:
    """Backward-compatible helper returning only the continuation slide."""
    remaining = [point for point in original.key_points if point not in moved_points]
    updated_source = original.model_copy(update={"key_points": remaining})
    plan = build_split_plan(
        original,
        updated_source,
        moved_points,
        "版面拆分",
    )
    return plan.primary_continuation
