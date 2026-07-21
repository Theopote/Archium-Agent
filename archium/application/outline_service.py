"""Outline planning helpers — audience adaptation and storyline mapping."""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from archium.application.outline_templates import detect_scenario_template, template_sections
from archium.application.presentation_manuscript_service import outline_plan_from_manuscript
from archium.domain.enums import NarrativeStage, OutlineAudienceMode
from archium.domain.narrative_arc import NarrativePosition
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.infrastructure.llm.presentation_schemas import (
    NarrativePositionDraft,
    OutlinePlanDraft,
    OutlineSectionDraft,
)

_AUDIENCE_CATEGORY_PRIORITY: dict[OutlineAudienceMode, tuple[str, ...]] = {
    OutlineAudienceMode.GOVERNMENT: (
        "decision",
        "implementation",
        "strategy",
        "problem",
        "heritage",
        "context",
        "technical",
        "culture",
        "intro",
        "general",
    ),
    OutlineAudienceMode.CLIENT: (
        "strategy",
        "problem",
        "context",
        "implementation",
        "decision",
        "technical",
        "heritage",
        "culture",
        "intro",
        "general",
    ),
    OutlineAudienceMode.EXPERT_REVIEW: (
        "technical",
        "heritage",
        "problem",
        "strategy",
        "context",
        "implementation",
        "decision",
        "culture",
        "intro",
        "general",
    ),
    OutlineAudienceMode.COMMUNITY: (
        "culture",
        "heritage",
        "problem",
        "strategy",
        "context",
        "implementation",
        "decision",
        "technical",
        "intro",
        "general",
    ),
    OutlineAudienceMode.INVESTOR: (
        "decision",
        "implementation",
        "strategy",
        "problem",
        "context",
        "technical",
        "heritage",
        "culture",
        "intro",
        "general",
    ),
    OutlineAudienceMode.CULTURE_TOURISM: (
        "culture",
        "heritage",
        "strategy",
        "implementation",
        "problem",
        "context",
        "decision",
        "technical",
        "intro",
        "general",
    ),
    OutlineAudienceMode.INTERNAL_DESIGN: (
        "strategy",
        "technical",
        "problem",
        "heritage",
        "context",
        "implementation",
        "decision",
        "culture",
        "intro",
        "general",
    ),
}


def infer_audience_mode(audience: str, purpose: str = "") -> OutlineAudienceMode:
    text = f"{audience} {purpose}"
    if any(k in text for k in ("政府", "主管部门", "文旅局", "规划部门")):
        return OutlineAudienceMode.GOVERNMENT
    if any(k in text for k in ("甲方", "建设单位", "业主")):
        return OutlineAudienceMode.CLIENT
    if any(k in text for k in ("内部", "设计团队")):
        return OutlineAudienceMode.INTERNAL_DESIGN
    if any(k in text for k in ("专家", "评审", "院士")):
        return OutlineAudienceMode.EXPERT_REVIEW
    if any(k in text for k in ("居民", "社区", "村民")):
        return OutlineAudienceMode.COMMUNITY
    if any(k in text for k in ("投资", "基金")):
        return OutlineAudienceMode.INVESTOR
    if any(k in text for k in ("文旅", "传播", "品牌", "游客")):
        return OutlineAudienceMode.CULTURE_TOURISM
    return OutlineAudienceMode.GOVERNMENT


def apply_audience_mode(outline: OutlinePlan, mode: OutlineAudienceMode) -> OutlinePlan:
    """Reorder sections and adjust emphasis for the target audience."""
    updated = deepcopy(outline)
    updated.audience_mode = mode
    priority = _AUDIENCE_CATEGORY_PRIORITY[mode]
    rank = {category: index for index, category in enumerate(priority)}

    def sort_key(section: OutlineSection) -> tuple[int, int]:
        return (rank.get(section.category, len(priority)), section.order)

    ordered = sorted(updated.sections, key=sort_key)
    for index, section in enumerate(ordered):
        section.order = index
        if mode == OutlineAudienceMode.EXPERT_REVIEW and section.category == "technical":
            section.required = True
            section.expanded = True
        if mode == OutlineAudienceMode.COMMUNITY and section.category == "decision":
            section.estimated_slide_count = min(section.estimated_slide_count, 1)
        if mode == OutlineAudienceMode.INVESTOR and section.category in {"decision", "implementation"}:
            section.required = True
    updated.sections = ordered
    updated.touch()
    return updated


def outline_from_storyline(
    brief: PresentationBrief,
    storyline: Storyline,
    *,
    audience_mode: OutlineAudienceMode | None = None,
) -> OutlinePlan:
    mode = audience_mode or infer_audience_mode(brief.audience, brief.purpose)
    sections = [
        OutlineSection(
            id=chapter.id,
            title=chapter.title,
            purpose=chapter.purpose,
            key_message=chapter.key_message,
            estimated_slide_count=chapter.estimated_slide_count,
            order=chapter.order,
            category="general",
        )
        for chapter in sorted(storyline.chapters, key=lambda item: item.order)
    ]
    outline = OutlinePlan(
        presentation_id=brief.presentation_id,
        title=brief.title,
        thesis=storyline.thesis,
        audience=brief.audience,
        purpose=brief.purpose,
        target_slide_count=brief.target_slide_count,
        audience_mode=mode,
        sections=sections,
    )
    return apply_audience_mode(outline, mode)


def merge_template_with_storyline(
    brief: PresentationBrief,
    storyline: Storyline,
) -> OutlinePlan:
    """Seed from scenario template and overlay storyline chapter messages where matched."""
    template_key = detect_scenario_template(
        required_sections=list(brief.required_sections),
        purpose=brief.purpose,
        audience=brief.audience,
    )
    if template_key is None:
        return outline_from_storyline(brief, storyline)

    sections = deepcopy(template_sections(template_key))
    chapter_by_title = {chapter.title.strip(): chapter for chapter in storyline.chapters}
    for section in sections:
        chapter = chapter_by_title.get(section.title.strip())
        if chapter is None:
            continue
        section.id = chapter.id
        section.key_message = chapter.key_message
        section.purpose = chapter.purpose
        section.estimated_slide_count = max(section.estimated_slide_count, chapter.estimated_slide_count)

    mode = infer_audience_mode(brief.audience, brief.purpose)
    outline = OutlinePlan(
        presentation_id=brief.presentation_id,
        title=brief.title,
        thesis=storyline.thesis,
        audience=brief.audience,
        purpose=brief.purpose,
        target_slide_count=brief.target_slide_count,
        audience_mode=mode,
        sections=sections,
    )
    return apply_audience_mode(outline, mode)


def outline_from_draft(
    draft: OutlinePlanDraft,
    *,
    presentation_id: UUID,
    version: int = 1,
) -> OutlinePlan:
    try:
        audience_mode = OutlineAudienceMode(draft.audience_mode)
    except ValueError:
        audience_mode = OutlineAudienceMode.GOVERNMENT

    sections = [
        OutlineSection(
            id=item.id,
            title=item.title,
            purpose=item.purpose,
            key_message=item.key_message,
            estimated_slide_count=item.estimated_slide_count,
            evidence_requirements=list(item.evidence_requirements),
            required_assets=list(item.required_assets),
            required=item.required,
            expanded=item.expanded,
            order=item.order,
            category=item.category,
            narrative_position=_narrative_position_from_draft(item.narrative_position),
        )
        for item in draft.sections
    ]
    return OutlinePlan(
        presentation_id=presentation_id,
        title=draft.title,
        thesis=draft.thesis,
        audience=draft.audience,
        purpose=draft.purpose,
        target_slide_count=draft.target_slide_count,
        audience_mode=audience_mode,
        sections=sections,
        version=version,
    )


def outline_from_manuscript(
    manuscript: PresentationManuscript,
    *,
    brief: PresentationBrief | None = None,
    audience: str = "",
    purpose: str = "",
) -> OutlinePlan:
    """Outline planning entry that reads PresentationManuscript sections."""
    return outline_plan_from_manuscript(
        manuscript,
        brief=brief,
        audience=audience,
        purpose=purpose,
    )


def section_to_draft(section: OutlineSection) -> OutlineSectionDraft:
    position = section.narrative_position
    return OutlineSectionDraft(
        id=section.id,
        title=section.title,
        purpose=section.purpose,
        key_message=section.key_message,
        estimated_slide_count=section.estimated_slide_count,
        evidence_requirements=list(section.evidence_requirements),
        required_assets=list(section.required_assets),
        required=section.required,
        expanded=section.expanded,
        order=section.order,
        category=section.category,
        narrative_position=(
            None
            if position is None
            else NarrativePositionDraft(
                stage=position.stage.value,
                advances_from_previous=position.advances_from_previous,
                prepares_for_next=position.prepares_for_next,
            )
        ),
    )


def _narrative_position_from_draft(
    draft: NarrativePositionDraft | None,
) -> NarrativePosition | None:
    if draft is None:
        return None
    try:
        stage = NarrativeStage(draft.stage.strip().casefold())
    except ValueError:
        stage = NarrativeStage.CONTEXT
    return NarrativePosition(
        stage=stage,
        advances_from_previous=draft.advances_from_previous.strip(),
        prepares_for_next=draft.prepares_for_next.strip(),
    )
