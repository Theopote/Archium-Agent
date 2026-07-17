"""LLM-assisted narrative slide split planning."""

from __future__ import annotations

from collections import Counter
from uuid import UUID, uuid4

from archium.agents._helpers import sanitize_slide_message
from archium.application.slide_repair_policy import loses_protected_content
from archium.application.slide_split_planner import (
    _allocate_citations,
    _allocate_visuals,
    citation_key,
)
from archium.application.slide_split_validator import validate_split_plan
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_split import SlideSplitPlan
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import SlideSplitDraft
from archium.logging import get_logger
from archium.prompts.slide_split import SLIDE_SPLIT_SYSTEM_PROMPT, build_slide_split_user_prompt

logger = get_logger(__name__, operation="slide_split_llm")

_MAX_KEY_POINTS = 5


def validate_llm_split_draft(original: SlideSpec, draft: SlideSplitDraft) -> tuple[bool, str]:
    """Reject LLM split proposals that drop facts or mis-assign key points."""
    if len(draft.source.key_points) > _MAX_KEY_POINTS:
        return False, "原页要点超过 5 条"
    if len(draft.continuation.key_points) > _MAX_KEY_POINTS:
        return False, "续页要点超过 5 条"
    if not draft.source.key_points and not draft.continuation.key_points:
        return False, "未分配任何要点"

    proposed = [*draft.source.key_points, *draft.continuation.key_points]
    if Counter(proposed) != Counter(original.key_points):
        return False, "要点分配与原文不一致"

    if not draft.source.message.strip() or not draft.continuation.message.strip():
        return False, "拆页方案缺少核心信息"

    combined_before = " ".join([original.message, *original.key_points])
    combined_after = " ".join(
        [
            draft.source.message,
            *draft.source.key_points,
            draft.continuation.message,
            *draft.continuation.key_points,
        ]
    )
    if loses_protected_content(combined_before, combined_after):
        return False, "拆页方案丢失了受保护信息"

    for label, indices in (
        ("source", draft.source.citation_indices),
        ("continuation", draft.continuation.citation_indices),
    ):
        for index in indices:
            if index < 0 or index >= len(original.source_citations):
                return False, f"{label} 引用了无效的 citation_index: {index}"

    assigned_citations = set(draft.source.citation_indices) | set(draft.continuation.citation_indices)
    if len(assigned_citations) != len(draft.source.citation_indices) + len(draft.continuation.citation_indices):
        return False, "同一引用被重复分配"

    for label, indices in (
        ("source", draft.source.visual_indices),
        ("continuation", draft.continuation.visual_indices),
    ):
        for index in indices:
            if index < 0 or index >= len(original.visual_requirements):
                return False, f"{label} 引用了无效的 visual_index: {index}"

    assigned_visuals = set(draft.source.visual_indices) | set(draft.continuation.visual_indices)
    if len(assigned_visuals) != len(draft.source.visual_indices) + len(draft.continuation.visual_indices):
        return False, "同一视觉素材被重复分配"

    return True, ""


def plan_from_llm_draft(
    original: SlideSpec,
    draft: SlideSplitDraft,
    reason: str,
    *,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
) -> SlideSplitPlan:
    """Materialize a validated LLM draft into a SlideSplitPlan."""
    source = original.model_copy(
        update={
            "title": draft.source.title.strip() or original.title,
            "message": sanitize_slide_message(draft.source.message),
            "key_points": list(draft.source.key_points),
            "source_citations": [],
            "visual_requirements": [],
        }
    )
    continuation = SlideSpec(
        id=uuid4(),
        presentation_id=original.presentation_id,
        chapter_id=original.chapter_id,
        order=original.order + 1,
        logical_key=build_slide_logical_key(original.chapter_id, original.order + 1),
        title=draft.continuation.title.strip() or f"{original.title}（续）",
        message=sanitize_slide_message(draft.continuation.message),
        slide_type=original.slide_type,
        layout_id=original.layout_id,
        key_points=list(draft.continuation.key_points),
        visual_requirements=[],
        source_citations=[],
        speaker_notes=None,
        status=original.status,
    )

    source, continuation, citation_mapping, asset_mapping = _apply_llm_resource_indices(
        original,
        source,
        continuation,
        draft,
    )

    plan = SlideSplitPlan(
        reason=f"{reason}；{draft.narrative_reason}（LLM 叙事规划）",
        source_slide_id=original.id,
        new_slides=[source, continuation],
        citation_mapping=citation_mapping,
        asset_mapping=asset_mapping,
        planning_source="llm",
    )
    return validate_split_plan(
        plan,
        original=original,
        storyline=storyline,
        chapter_slide_count=chapter_slide_count,
    )


def try_build_llm_split_plan(
    original: SlideSpec,
    reason: str,
    *,
    llm: LLMProvider,
    settings: Settings | None = None,
    brief: PresentationBrief | None = None,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
) -> SlideSplitPlan | None:
    """Ask the LLM for a narrative split plan; return None when proposal is unusable."""
    runtime_settings = settings or get_settings()
    try:
        draft = llm.generate_structured(
            LLMRequest(
                system_prompt=SLIDE_SPLIT_SYSTEM_PROMPT,
                user_prompt=build_slide_split_user_prompt(
                    slide_summary=_slide_summary(original),
                    split_trigger=reason,
                    key_points_numbered=_numbered_key_points(original.key_points),
                    citations_numbered=_numbered_citations(original),
                    visuals_numbered=_numbered_visuals(original),
                    chapter_summary=_chapter_summary(original, storyline),
                    brief_summary=_brief_summary(brief),
                ),
                model=runtime_settings.llm_model,
                temperature=0.3,
                json_mode=True,
            ),
            SlideSplitDraft,
        )
    except Exception as exc:
        logger.warning("LLM slide split planning failed for slide %s: %s", original.id, exc)
        return None

    valid, reject_reason = validate_llm_split_draft(original, draft)
    if not valid:
        logger.info(
            "Rejected LLM split draft for slide %s: %s",
            original.id,
            reject_reason,
        )
        return None

    return plan_from_llm_draft(
        original,
        draft,
        reason,
        storyline=storyline,
        chapter_slide_count=chapter_slide_count,
    )


def choose_split_plan(rule_plan: SlideSplitPlan, llm_plan: SlideSplitPlan | None) -> SlideSplitPlan:
    """Prefer a validated LLM plan when it clears structural checks."""
    if llm_plan is None:
        return rule_plan
    if not llm_plan.requires_human_approval:
        return llm_plan
    if not rule_plan.requires_human_approval:
        return rule_plan
    return llm_plan


def _apply_llm_resource_indices(
    original: SlideSpec,
    source: SlideSpec,
    continuation: SlideSpec,
    draft: SlideSplitDraft,
) -> tuple[SlideSpec, SlideSpec, dict[str, UUID], dict[int, UUID]]:
    citation_mapping: dict[str, UUID] = {}
    asset_mapping: dict[int, UUID] = {}

    if original.source_citations:
        if draft.source.citation_indices or draft.continuation.citation_indices:
            source_citations = [
                original.source_citations[index] for index in draft.source.citation_indices
            ]
            continuation_citations = [
                original.source_citations[index] for index in draft.continuation.citation_indices
            ]
            for index in draft.source.citation_indices:
                citation = original.source_citations[index]
                citation_mapping[citation_key(citation.document_id, citation.chunk_id, index)] = (
                    source.id
                )
            for index in draft.continuation.citation_indices:
                citation = original.source_citations[index]
                citation_mapping[citation_key(citation.document_id, citation.chunk_id, index)] = (
                    continuation.id
                )
            unassigned = [
                index
                for index in range(len(original.source_citations))
                if index not in draft.source.citation_indices
                and index not in draft.continuation.citation_indices
            ]
            if unassigned:
                source_citations, continuation_citations, citation_mapping = _allocate_citations(
                    original,
                    source.model_copy(update={"source_citations": source_citations}),
                    continuation.model_copy(update={"source_citations": continuation_citations}),
                    draft.continuation.key_points,
                )
        else:
            source_citations, continuation_citations, citation_mapping = _allocate_citations(
                original,
                source,
                continuation,
                draft.continuation.key_points,
            )
        source = source.model_copy(update={"source_citations": source_citations})
        continuation = continuation.model_copy(update={"source_citations": continuation_citations})

    if original.visual_requirements:
        if draft.source.visual_indices or draft.continuation.visual_indices:
            source_visuals = [
                original.visual_requirements[index] for index in draft.source.visual_indices
            ]
            continuation_visuals = [
                original.visual_requirements[index] for index in draft.continuation.visual_indices
            ]
            for index in draft.source.visual_indices:
                asset_mapping[index] = source.id
            for index in draft.continuation.visual_indices:
                asset_mapping[index] = continuation.id
            unassigned = [
                index
                for index in range(len(original.visual_requirements))
                if index not in draft.source.visual_indices
                and index not in draft.continuation.visual_indices
            ]
            if unassigned:
                source_visuals, continuation_visuals, asset_mapping = _allocate_visuals(
                    original,
                    source,
                    continuation,
                    draft.continuation.key_points,
                )
        else:
            source_visuals, continuation_visuals, asset_mapping = _allocate_visuals(
                original,
                source,
                continuation,
                draft.continuation.key_points,
            )
        source = source.model_copy(update={"visual_requirements": source_visuals})
        continuation = continuation.model_copy(
            update={"visual_requirements": continuation_visuals}
        )

    return source, continuation, citation_mapping, asset_mapping


def _slide_summary(slide: SlideSpec) -> str:
    points = "\n".join(f"- {point}" for point in slide.key_points) or "（无要点）"
    return (
        f"第 {slide.order + 1} 页\n"
        f"标题: {slide.title}\n"
        f"核心信息: {slide.message}\n"
        f"要点:\n{points}"
    )


def _numbered_key_points(key_points: list[str]) -> str:
    return "\n".join(f"{index}. {point}" for index, point in enumerate(key_points))


def _numbered_citations(slide: SlideSpec) -> str:
    if not slide.source_citations:
        return ""
    lines: list[str] = []
    for index, citation in enumerate(slide.source_citations):
        quote = citation.quote or "（无摘录）"
        lines.append(f"{index}. {citation.document_name} — {quote}")
    return "\n".join(lines)


def _numbered_visuals(slide: SlideSpec) -> str:
    if not slide.visual_requirements:
        return ""
    return "\n".join(
        f"{index}. [{item.type.value}] {item.description}"
        for index, item in enumerate(slide.visual_requirements)
    )


def _chapter_summary(slide: SlideSpec, storyline: Storyline | None) -> str:
    if storyline is None:
        return "（无 Storyline 上下文）"
    chapter = next((item for item in storyline.chapters if item.id == slide.chapter_id), None)
    if chapter is None:
        return "（未找到对应章节）"
    return (
        f"章节: {chapter.title}\n"
        f"章节目的: {chapter.purpose}\n"
        f"章节核心信息: {chapter.key_message}\n"
        f"Storyline 论点: {storyline.thesis}\n"
        f"章节页数预算: {chapter.estimated_slide_count}"
    )


def _brief_summary(brief: PresentationBrief | None) -> str:
    if brief is None:
        return "（无 Brief）"
    return f"标题: {brief.title}\n核心信息: {brief.core_message}\n目的: {brief.purpose}"
