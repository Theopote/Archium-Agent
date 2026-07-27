"""Seed a starter outline + first-page draft after project genesis (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.outline_service import infer_audience_mode
from archium.application.outline_templates import detect_scenario_template, template_sections
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode, SlideStatus, SlideType
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Presentation
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_intent import SlideIntent
from archium.domain.slide_role import SlideRole, visual_strategy_from_role
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository


@dataclass(frozen=True)
class GenesisStarterResult:
    created: bool
    presentation_id: UUID
    outline_id: UUID | None
    page_count: int
    has_first_slide: bool
    slides_ready_count: int = 0
    layout_ready_count: int = 0
    has_cover_layout: bool = False
    cover_preview_path: str | None = None
    summary: str = ""


_GENERIC_STARTER: tuple[tuple[str, str, str, str], ...] = (
    ("cover", "封面", "intro", "确立汇报主题与对象"),
    ("context", "背景与语境", "context", "说明项目背景与基地语境"),
    ("problem", "问题与机遇", "problem", "明确核心问题或改造动因"),
    ("strategy", "设计策略", "strategy", "提出总体设计策略"),
    ("spatial", "空间与效果", "strategy", "展示空间组织或预期效果"),
    ("closing", "总结与下一步", "decision", "汇总结论与决策事项"),
)

_ROLE_BY_CATEGORY: dict[str, SlideRole] = {
    "intro": SlideRole.OPENING,
    "context": SlideRole.BACKGROUND,
    "problem": SlideRole.PROBLEM_ANALYSIS,
    "strategy": SlideRole.STRATEGY,
    "decision": SlideRole.CONCLUSION,
}

_SLIDE_TYPE_BY_ROLE: dict[SlideRole, SlideType] = {
    SlideRole.OPENING: SlideType.TITLE,
    SlideRole.CONCLUSION: SlideType.CLOSING,
    SlideRole.SUMMARY: SlideType.SUMMARY,
    SlideRole.BACKGROUND: SlideType.SECTION,
    SlideRole.DATA: SlideType.DATA,
    SlideRole.COMPARISON: SlideType.COMPARISON,
    SlideRole.TIMELINE: SlideType.TIMELINE,
    SlideRole.EXPERIENCE: SlideType.IMAGE,
    SlideRole.VISION: SlideType.IMAGE,
    SlideRole.CONCEPT: SlideType.IMAGE,
}


def _slide_type_for_role(role: SlideRole | None) -> SlideType:
    if role is None:
        return SlideType.CONTENT
    return _SLIDE_TYPE_BY_ROLE.get(role, SlideType.CONTENT)


def _section_by_id(sections: list[OutlineSection]) -> dict[str, OutlineSection]:
    return {section.id: section for section in sections}


def _placeholder_message(*, intent: SlideIntent, section: OutlineSection | None) -> str:
    for candidate in (
        (intent.central_conclusion or "").strip(),
        (section.key_message if section is not None else "").strip(),
        (section.purpose if section is not None else "").strip(),
        (intent.page_task or "").strip(),
    ):
        if candidate:
            return candidate[:500]
    return "本页核心结论待补充"


def _placeholder_title(
    *,
    intent: SlideIntent,
    section: OutlineSection | None,
    project_title: str,
    order: int,
) -> str:
    if order == 0:
        return project_title
    for candidate in (
        (intent.page_task or "").strip(),
        (section.title if section is not None else "").strip(),
    ):
        if candidate:
            return candidate[:500]
    return f"第 {order + 1} 页"


def _ensure_starter_slides(
    presentations: PresentationRepository,
    *,
    presentation_id: UUID,
    page_intents: list[SlideIntent],
    sections: list[OutlineSection],
    project_title: str,
    cover_message_override: str | None = None,
) -> int:
    """Create placeholder SlideSpec rows for each outline page intent (no LLM)."""
    existing = {
        slide.order: slide
        for slide in presentations.list_slides(presentation_id)
    }
    section_map = _section_by_id(sections)
    created = 0
    for intent in sorted(page_intents, key=lambda item: item.order):
        order = int(intent.order)
        if order in existing:
            continue
        section = section_map.get(intent.chapter_id)
        role = intent.slide_role or _ROLE_BY_CATEGORY.get(
            section.category if section is not None else "",
            SlideRole.OTHER,
        )
        if order == 0 and cover_message_override:
            message = cover_message_override.strip()[:500]
        else:
            message = _placeholder_message(intent=intent, section=section)
        slide = SlideSpec(
            presentation_id=presentation_id,
            chapter_id=intent.chapter_id,
            order=order,
            title=_placeholder_title(
                intent=intent,
                section=section,
                project_title=project_title,
                order=order,
            ),
            message=message,
            slide_type=_slide_type_for_role(role),
            slide_role=role,
            visual_strategy=intent.visual_strategy or visual_strategy_from_role(role),
            logical_key=build_slide_logical_key(intent.chapter_id, order),
            status=SlideStatus.PLANNED,
        )
        presentations.save_slide(slide)
        created += 1
    return created


def _starter_summary(
    *,
    page_count: int,
    slides_ready_count: int,
    layout_ready_count: int,
    has_cover_layout: bool,
    created: bool,
) -> str:
    if created:
        lead = f"已生成 {page_count} 页大纲草稿"
    else:
        lead = f"已有 {page_count} 页大纲草稿"
    if slides_ready_count >= page_count:
        lead += f"，{slides_ready_count} 页内容占位已就绪"
    elif slides_ready_count > 0:
        lead += f"，{slides_ready_count}/{page_count} 页内容占位已就绪"
    if layout_ready_count >= page_count and layout_ready_count > 0:
        lead += f"，全稿 {layout_ready_count} 页版式线框已就绪"
    elif layout_ready_count > 0:
        lead += f"，{layout_ready_count}/{page_count} 页版式线框已就绪"
    elif has_cover_layout:
        lead += "，封面版式线框已就绪"
    elif slides_ready_count > 0:
        lead += "，封面页可预览"
    return lead


def _starter_sections(*, prompt: str, purpose: str) -> list[OutlineSection]:
    template_key = detect_scenario_template(purpose=purpose, audience="", required_sections=[])
    if template_key is not None:
        sections = template_sections(template_key)
        return sections[:8]
    sections: list[OutlineSection] = []
    for order, (section_id, title, category, key_message) in enumerate(_GENERIC_STARTER):
        sections.append(
            OutlineSection(
                id=section_id,
                title=title,
                purpose=key_message,
                key_message=key_message,
                order=order,
                estimated_slide_count=1,
                category=category,
                expanded=True,
            )
        )
    if prompt.strip():
        _ = prompt  # reserved for future keyword enrichment
    return sections


def _page_intents_from_sections(sections: list[OutlineSection]) -> list[SlideIntent]:
    intents: list[SlideIntent] = []
    order = 0
    for section in sorted(sections, key=lambda item: item.order):
        for _ in range(max(1, section.estimated_slide_count)):
            role = _ROLE_BY_CATEGORY.get(section.category, SlideRole.OTHER)
            intents.append(
                SlideIntent(
                    order=order,
                    chapter_id=section.id,
                    page_task=section.title,
                    central_conclusion=section.key_message,
                    slide_role=role,
                    visual_strategy=visual_strategy_from_role(role),
                )
            )
            order += 1
    return intents


def _thesis_from(*, prompt: str, understanding: str, project_name: str) -> str:
    for candidate in (understanding.strip(), prompt.strip(), project_name.strip()):
        if candidate:
            line = candidate.splitlines()[0].strip()
            if len(line) >= 8:
                return line[:200]
            if line:
                return line
    return "建筑汇报核心论点待补充"


def _existing_starter(session: Session, project_id: UUID) -> GenesisStarterResult | None:
    presentations = PresentationRepository(session).list_by_project(project_id)
    if not presentations:
        return None
    presentation = presentations[0]
    outlines = PresentationRepository(session).list_outlines(presentation.id)
    outline = outlines[0] if outlines else None
    slides = PresentationRepository(session).list_slides(presentation.id)
    if outline is None or not outline.sections:
        return None
    page_count = len(outline.page_intents) or len(outline.sections)
    slides_ready_count = len(slides)
    layout_ready_count = sum(1 for item in slides if item.layout_plan_id is not None)
    from archium.application.genesis_cover_layout_service import (
        cover_wireframe_preview_path,
        ensure_deck_wireframe_layouts,
    )

    preview_path = cover_wireframe_preview_path(session, presentation.id)
    has_cover = preview_path is not None or (
        bool(slides) and slides[0].layout_plan_id is not None
    )
    if slides_ready_count < page_count:
        added = _ensure_starter_slides(
            PresentationRepository(session),
            presentation_id=presentation.id,
            page_intents=list(outline.page_intents),
            sections=list(outline.sections),
            project_title=presentation.title or "新汇报",
        )
        if added:
            session.commit()
            slides = PresentationRepository(session).list_slides(presentation.id)
            slides_ready_count = len(slides)
            layout_ready_count = sum(
                1 for item in slides if item.layout_plan_id is not None
            )
    if layout_ready_count < slides_ready_count:
        deck = ensure_deck_wireframe_layouts(
            session,
            project_id=project_id,
            presentation_id=presentation.id,
        )
        slides = PresentationRepository(session).list_slides(presentation.id)
        layout_ready_count = deck.layout_ready_count
        preview_path = deck.cover_preview_path or preview_path
        has_cover = has_cover or layout_ready_count > 0
    summary = _starter_summary(
        page_count=page_count,
        slides_ready_count=slides_ready_count,
        layout_ready_count=layout_ready_count,
        has_cover_layout=has_cover,
        created=False,
    )
    return GenesisStarterResult(
        created=False,
        presentation_id=presentation.id,
        outline_id=outline.id,
        page_count=page_count,
        has_first_slide=bool(slides),
        slides_ready_count=slides_ready_count,
        layout_ready_count=layout_ready_count,
        has_cover_layout=has_cover,
        cover_preview_path=preview_path,
        summary=summary,
    )


def get_genesis_starter_state(
    session: Session,
    project_id: UUID,
) -> GenesisStarterResult | None:
    """Return starter draft metadata when the project has a genesis outline."""
    return _existing_starter(session, project_id)


def ensure_genesis_starter_draft(
    session: Session,
    project_id: UUID,
    *,
    prompt: str,
    project_name: str,
    understanding_summary: str = "",
) -> GenesisStarterResult:
    """Create presentation + outline + first SlideSpec when genesis completes.

    Idempotent: returns existing draft when the project already has an outline.
    """
    existing = _existing_starter(session, project_id)
    if existing is not None:
        return existing

    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    presentations = PresentationRepository(session)
    title = (project_name or project.name or "新汇报").strip() or "新汇报"
    presentation = presentations.create_presentation(
        Presentation(project_id=project_id, title=title)
    )

    purpose = understanding_summary.strip() or prompt.strip() or title
    sections = _starter_sections(prompt=prompt, purpose=purpose)
    page_intents = _page_intents_from_sections(sections)
    audience_mode = infer_audience_mode("", purpose)
    outline = OutlinePlan(
        presentation_id=presentation.id,
        title=title,
        thesis=_thesis_from(
            prompt=prompt,
            understanding=understanding_summary,
            project_name=title,
        ),
        audience="汇报对象待确认",
        purpose=purpose[:500] if purpose else "建筑方案汇报",
        target_slide_count=max(len(page_intents), 6),
        audience_mode=audience_mode or OutlineAudienceMode.GOVERNMENT,
        sections=sections,
        page_intents=page_intents,
        approval_status=ApprovalStatus.DRAFT,
    )
    saved_outline = presentations.save_outline(outline)
    presentation.current_outline_id = saved_outline.id
    presentations.update_presentation(presentation)

    first_intent = page_intents[0]
    cover_message = (
        first_intent.central_conclusion.strip()
        or understanding_summary.strip()[:160]
        or prompt.strip()[:160]
        or "汇报核心主张待补充"
    )
    slides_added = _ensure_starter_slides(
        presentations,
        presentation_id=presentation.id,
        page_intents=page_intents,
        sections=sections,
        project_title=title,
        cover_message_override=cover_message,
    )

    from archium.application.genesis_cover_layout_service import ensure_deck_wireframe_layouts

    deck = ensure_deck_wireframe_layouts(
        session,
        project_id=project_id,
        presentation_id=presentation.id,
    )

    slides_ready_count = len(presentations.list_slides(presentation.id))
    page_count = len(page_intents)
    layout_ready_count = deck.layout_ready_count
    has_cover_layout = bool(deck.cover_preview_path or layout_ready_count > 0)
    summary = _starter_summary(
        page_count=page_count,
        slides_ready_count=slides_ready_count,
        layout_ready_count=layout_ready_count,
        has_cover_layout=has_cover_layout,
        created=True,
    )
    return GenesisStarterResult(
        created=True,
        presentation_id=presentation.id,
        outline_id=saved_outline.id,
        page_count=page_count,
        has_first_slide=slides_ready_count > 0,
        slides_ready_count=slides_ready_count,
        layout_ready_count=layout_ready_count,
        has_cover_layout=has_cover_layout,
        cover_preview_path=deck.cover_preview_path,
        summary=summary,
    )
