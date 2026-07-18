"""LLM-assisted review helpers and prompt formatting."""

from __future__ import annotations

from uuid import UUID

from archium.application.chunk_models import ProjectContextBundle
from archium.config.settings import Settings
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import (
    BriefAlignmentDraft,
    ProfessionalReviewDraft,
    ReviewIssueDraft,
)
from archium.logging import get_logger
from archium.prompts.brief_alignment import (
    BRIEF_ALIGNMENT_SYSTEM_PROMPT,
    build_brief_alignment_user_prompt,
)
from archium.prompts.layer_review import (
    LAYER_REVIEW_SYSTEM_PROMPT,
    build_layer_review_user_prompt,
)

logger = get_logger(__name__, operation="automated_review")


def llm_rule_code(item: ReviewIssueDraft) -> str:
    raw = (item.rule_code or "").strip()
    if raw:
        return raw.upper()
    layer = item.reviewer_layer.strip().upper() or "UNKNOWN"
    category = item.category.strip().upper() or "OTHER"
    return f"LLM.{layer}.{category}"


def parse_review_layer(value: str) -> ReviewLayer:
    try:
        return ReviewLayer(value.strip().lower())
    except ValueError:
        return ReviewLayer.ARCHITECTURAL


def parse_review_category(value: str) -> ReviewCategory:
    try:
        return ReviewCategory(value.strip().lower())
    except ValueError:
        return ReviewCategory.OTHER


def parse_review_severity(value: str) -> ReviewSeverity:
    try:
        return ReviewSeverity(value.strip().lower())
    except ValueError:
        return ReviewSeverity.SUGGESTION


def format_brief_summary(brief: PresentationBrief) -> str:
    sections = ", ".join(brief.required_sections) or "无"
    decisions = ", ".join(brief.decisions_required) or "无"
    return (
        f"标题: {brief.title}\n"
        f"核心信息: {brief.core_message}\n"
        f"必要章节: {sections}\n"
        f"需决策事项: {decisions}\n"
        f"受众: {brief.audience}\n"
        f"目的: {brief.purpose}"
    )


def format_storyline_summary(storyline: Storyline) -> str:
    chapters = ", ".join(
        f"{chapter.id}:{chapter.title}({chapter.key_message})"
        for chapter in storyline.chapters
    )
    return f"论点: {storyline.thesis}\n章节: {chapters}"


def format_context_summary(context_bundle: ProjectContextBundle | None) -> str:
    if context_bundle is None or not context_bundle.chunks:
        return "无项目资料片段"
    lines = []
    for chunk in context_bundle.chunks[:8]:
        label = chunk.section_title or f"chunk-{chunk.chunk_index}"
        preview = chunk.content.strip().replace("\n", " ")[:120]
        lines.append(f"- [{label}] {preview}")
    return "\n".join(lines)


def format_slides_summary(slides: list[SlideSpec], *, include_key_points: bool = False) -> str:
    lines: list[str] = []
    for slide in sorted(slides, key=lambda item: item.order):
        line = f"p{slide.order + 1} [{slide.slide_type.value}] {slide.title}: {slide.message}"
        if include_key_points and slide.key_points:
            line += " | 要点: " + "; ".join(slide.key_points[:5])
        if slide.source_citations:
            line += f" | 引用: {len(slide.source_citations)}"
        if slide.visual_requirements:
            visuals = ", ".join(req.type.value for req in slide.visual_requirements)
            line += f" | 视觉: {visuals}"
        lines.append(line)
    return "\n".join(lines)


def run_llm_brief_alignment(
    llm: LLMProvider,
    settings: Settings,
    presentation_id: UUID,
    brief: PresentationBrief,
    slides: list[SlideSpec],
) -> tuple[ReviewIssue | None, bool]:
    brief_summary = format_brief_summary(brief)
    slides_summary = format_slides_summary(slides)
    request = LLMRequest(
        system_prompt=BRIEF_ALIGNMENT_SYSTEM_PROMPT,
        user_prompt=build_brief_alignment_user_prompt(
            brief_summary=brief_summary,
            slides_summary=slides_summary,
        ),
        model=settings.llm_model,
        temperature=0.1,
        json_mode=True,
    )
    try:
        draft = llm.generate_structured(request, BriefAlignmentDraft)
    except Exception as exc:
        logger.warning("LLM Brief alignment check failed: %s", exc)
        return None, False

    if draft.aligned:
        return None, True

    gap = draft.gap_summary.strip() or "Slide 结论与 Brief 核心诉求存在语义偏差。"
    severity = ReviewSeverity.HIGH if draft.confidence >= 0.75 else ReviewSeverity.MEDIUM
    return (
        ReviewIssue(
            presentation_id=presentation_id,
            reviewer_layer=ReviewLayer.CONTENT,
            category=ReviewCategory.COVERAGE,
            severity=severity,
            rule_code=ReviewRuleCode.CONTENT_BRIEF_ALIGNMENT_GAP,
            title="Brief 语义对齐不足",
            description=gap,
            suggestion=draft.suggestion or "调整各页结论，确保与 Brief 核心信息一致。",
        ),
        True,
    )


def run_llm_multi_layer_review(
    llm: LLMProvider,
    settings: Settings,
    presentation_id: UUID,
    slides: list[SlideSpec],
    *,
    brief: PresentationBrief | None,
    storyline: Storyline | None,
    context_bundle: ProjectContextBundle | None = None,
) -> list[ReviewIssue]:
    brief_summary = format_brief_summary(brief) if brief is not None else "无 Brief"
    storyline_summary = (
        format_storyline_summary(storyline) if storyline is not None else "无 Storyline"
    )
    context_summary = format_context_summary(context_bundle)
    slides_summary = format_slides_summary(slides, include_key_points=True)
    request = LLMRequest(
        system_prompt=LAYER_REVIEW_SYSTEM_PROMPT,
        user_prompt=build_layer_review_user_prompt(
            brief_summary=brief_summary,
            storyline_summary=storyline_summary,
            slides_summary=slides_summary,
            context_summary=context_summary,
        ),
        model=settings.llm_model,
        temperature=0.2,
        json_mode=True,
    )
    try:
        draft = llm.generate_structured(request, ProfessionalReviewDraft)
    except Exception as exc:
        logger.warning("LLM multi-layer review failed: %s", exc)
        return []

    slides_by_order = {slide.order: slide for slide in slides}
    issues: list[ReviewIssue] = []
    for item in draft.issues:
        slide = slides_by_order.get(item.slide_order) if item.slide_order is not None else None
        issues.append(
            ReviewIssue(
                presentation_id=presentation_id,
                slide_id=slide.id if slide is not None else None,
                reviewer_layer=parse_review_layer(item.reviewer_layer),
                category=parse_review_category(item.category),
                severity=parse_review_severity(item.severity),
                rule_code=llm_rule_code(item),
                title=item.title.strip(),
                description=item.description.strip(),
                suggestion=item.suggestion.strip() if item.suggestion else None,
            )
        )
    return issues
