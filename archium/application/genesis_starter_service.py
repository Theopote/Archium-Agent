"""Seed a starter outline + first-page draft after project genesis (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.outline_service import infer_audience_mode
from archium.application.outline_templates import detect_scenario_template, template_sections
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode, SlideType
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
    summary: str


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
    return GenesisStarterResult(
        created=False,
        presentation_id=presentation.id,
        outline_id=outline.id,
        page_count=page_count,
        has_first_slide=bool(slides),
        summary=f"已有 {page_count} 页大纲草稿",
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
    first_section = sections[0]
    cover_message = (
        first_intent.central_conclusion.strip()
        or understanding_summary.strip()[:160]
        or prompt.strip()[:160]
        or "汇报核心主张待补充"
    )
    slide = SlideSpec(
        presentation_id=presentation.id,
        chapter_id=first_section.id,
        order=0,
        title=title,
        message=cover_message,
        slide_type=SlideType.TITLE,
        slide_role=SlideRole.OPENING,
        visual_strategy=visual_strategy_from_role(SlideRole.OPENING),
        logical_key=build_slide_logical_key(first_section.id, 0),
    )
    presentations.save_slide(slide)
    session.commit()

    page_count = len(page_intents)
    return GenesisStarterResult(
        created=True,
        presentation_id=presentation.id,
        outline_id=saved_outline.id,
        page_count=page_count,
        has_first_slide=True,
        summary=f"已生成 {page_count} 页大纲草稿，封面页可预览",
    )
