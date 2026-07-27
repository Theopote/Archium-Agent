"""Generate starter-deck wireframe layouts after genesis (rule-based, no LLM)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.slide_preview_service import SlidePreviewService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)

logger = logging.getLogger(__name__)

_PAGE_WIDTH = 13.333
_PAGE_HEIGHT = 7.5


@dataclass(frozen=True)
class GenesisSlideWireframeResult:
    applied: bool
    slide_id: UUID | None
    layout_plan_id: UUID | None
    preview_path: str | None
    summary: str


# Backward-compatible alias
GenesisCoverLayoutResult = GenesisSlideWireframeResult


@dataclass(frozen=True)
class GenesisDeckWireframeResult:
    applied_count: int
    skipped_count: int
    failed_count: int
    layout_ready_count: int
    cover_preview_path: str | None
    summary: str


def _fallback_textual_layout(
    *,
    slide: SlideSpec,
    visual_intent_id: UUID,
    design_system_id: UUID,
) -> LayoutPlan:
    """Minimal title + body layout when capacity/planner returns no candidates."""
    title = (slide.title or f"P{slide.order + 1}").strip()[:120]
    body = (slide.message or "本页核心结论待补充").strip()[:280]
    title_id = f"genesis-title-{slide.order}"
    body_id = f"genesis-body-{slide.order}"
    return LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="genesis_fallback",
        page_width=_PAGE_WIDTH,
        page_height=_PAGE_HEIGHT,
        hero_element_id=title_id,
        reading_order=[title_id, body_id],
        whitespace_ratio=0.35,
        elements=[
            LayoutElement(
                id=title_id,
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=title,
                x=0.8,
                y=1.2,
                width=11.7,
                height=1.2,
                z_index=2,
            ),
            LayoutElement(
                id=body_id,
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content=body,
                x=0.8,
                y=2.8,
                width=11.7,
                height=3.2,
                z_index=1,
            ),
        ],
        design_system_id=design_system_id,
        visual_intent_id=visual_intent_id,
    )


def cover_wireframe_preview_path(
    session: Session,
    presentation_id: UUID,
) -> str | None:
    """Return cached wireframe PNG for the first slide when a layout exists."""
    presentations = PresentationRepository(session)
    slides = sorted(
        presentations.list_slides(presentation_id),
        key=lambda item: item.order,
    )
    if not slides or slides[0].layout_plan_id is None:
        return None
    plan = LayoutPlanRepository(session).get(slides[0].layout_plan_id)
    if plan is None:
        return None
    path = SlidePreviewService()._ensure_wireframe_preview(presentation_id, plan)
    if path is not None and path.is_file():
        return str(path)
    return None


def _resolve_design_system(session: Session) -> object:
    design_repo = DesignSystemRepository(session)
    design = design_repo.get(default_presentation_design_system().id)
    if design is None:
        design = design_repo.save(default_presentation_design_system())
    return design


def _ensure_slide_wireframe_layout(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID,
    slide: SlideSpec,
    settings: Settings,
    design_system: object,
    commit: bool,
) -> GenesisSlideWireframeResult:
    """Rule-based VisualIntent + LayoutPlan + wireframe PNG for one slide."""
    presentations = PresentationRepository(session)
    plans = LayoutPlanRepository(session)
    preview_service = SlidePreviewService(settings)

    if slide.layout_plan_id is not None:
        plan = plans.get(slide.layout_plan_id)
        if plan is not None:
            wireframe = preview_service._ensure_wireframe_preview(presentation_id, plan)
            if wireframe is not None and wireframe.is_file():
                return GenesisSlideWireframeResult(
                    applied=False,
                    slide_id=slide.id,
                    layout_plan_id=plan.id,
                    preview_path=str(wireframe),
                    summary=f"P{slide.order + 1} 版式线框已就绪",
                )

    nested = session.begin_nested() if session.in_transaction() else None
    try:
        intent_service = VisualIntentService(session, llm=None, settings=settings)
        intent = intent_service.generate_for_slide(slide, use_llm=False)
        intent = VisualIntentRepository(session).save(intent)
        slide.visual_intent_id = intent.id
        presentations.save_slide(slide)

        planner = LayoutPlanningService(session, llm=None, settings=settings)
        try:
            plan = planner.plan_slide(
                slide=slide,
                visual_intent_id=intent.id,
                art_direction_id=intent.art_direction_id,
                design_system_id=design_system.id,
                candidate_count=1,
                project_id=project_id,
            )
        except ValueError as exc:
            logger.warning(
                "Genesis planner returned no candidates for slide %s; using fallback: %s",
                slide.id,
                exc,
            )
            plan = LayoutPlanRepository(session).save(
                _fallback_textual_layout(
                    slide=slide,
                    visual_intent_id=intent.id,
                    design_system_id=design_system.id,
                )
            )
        slide.layout_plan_id = plan.id
        presentations.save_slide(slide)

        LayoutValidationService().validate(plan, design_system)

        wireframe = preview_service._ensure_wireframe_preview(presentation_id, plan)
        preview_path = str(wireframe) if wireframe is not None and wireframe.is_file() else None
        if nested is not None:
            nested.commit()
        if commit:
            session.commit()
        return GenesisSlideWireframeResult(
            applied=True,
            slide_id=slide.id,
            layout_plan_id=plan.id,
            preview_path=preview_path,
            summary=f"P{slide.order + 1} 版式线框已生成",
        )
    except Exception as exc:
        logger.exception(
            "Genesis wireframe failed for slide %s (presentation %s): %s",
            slide.id,
            presentation_id,
            exc,
        )
        if nested is not None:
            nested.rollback()
        elif commit:
            session.rollback()
        return GenesisSlideWireframeResult(
            applied=False,
            slide_id=slide.id,
            layout_plan_id=None,
            preview_path=None,
            summary=f"P{slide.order + 1} 线框生成跳过",
        )


def ensure_cover_wireframe_layout(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings | None = None,
) -> GenesisSlideWireframeResult:
    """Rule-based wireframe for the cover slide only."""
    resolved = settings or get_settings()
    presentations = PresentationRepository(session)
    slides = sorted(
        presentations.list_slides(presentation_id),
        key=lambda item: item.order,
    )
    if not slides:
        return GenesisSlideWireframeResult(
            applied=False,
            slide_id=None,
            layout_plan_id=None,
            preview_path=None,
            summary="尚无封面页，跳过版式生成",
        )
    design = _resolve_design_system(session)
    return _ensure_slide_wireframe_layout(
        session,
        project_id=project_id,
        presentation_id=presentation_id,
        slide=slides[0],
        settings=resolved,
        design_system=design,
        commit=True,
    )


def ensure_deck_wireframe_layouts(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings | None = None,
    max_slides: int | None = None,
) -> GenesisDeckWireframeResult:
    """Generate rule-based wireframes for all slides missing LayoutPlan."""
    resolved = settings or get_settings()
    presentations = PresentationRepository(session)
    slides = sorted(
        presentations.list_slides(presentation_id),
        key=lambda item: item.order,
    )
    if not slides:
        return GenesisDeckWireframeResult(
            applied_count=0,
            skipped_count=0,
            failed_count=0,
            layout_ready_count=0,
            cover_preview_path=None,
            summary="尚无页面，跳过版式生成",
        )

    if max_slides is not None:
        slides = slides[: max(0, max_slides)]

    design = _resolve_design_system(session)
    applied = 0
    skipped = 0
    failed = 0
    cover_preview: str | None = None

    for slide in slides:
        if slide.layout_plan_id is not None:
            plans = LayoutPlanRepository(session)
            plan = plans.get(slide.layout_plan_id)
            if plan is not None:
                wireframe = SlidePreviewService(resolved)._ensure_wireframe_preview(
                    presentation_id, plan
                )
                if wireframe is not None and wireframe.is_file() and slide.order == 0:
                    cover_preview = str(wireframe)
            skipped += 1
            continue

        result = _ensure_slide_wireframe_layout(
            session,
            project_id=project_id,
            presentation_id=presentation_id,
            slide=slide,
            settings=resolved,
            design_system=design,
            commit=False,
        )
        if result.layout_plan_id is not None:
            applied += 1
            if slide.order == 0 and result.preview_path:
                cover_preview = result.preview_path
        else:
            failed += 1

    try:
        session.commit()
    except Exception:
        logger.exception("Genesis deck wireframe batch commit failed")
        session.rollback()

    refreshed = presentations.list_slides(presentation_id)
    layout_ready_count = sum(1 for item in refreshed if item.layout_plan_id is not None)
    if cover_preview is None:
        cover_preview = cover_wireframe_preview_path(session, presentation_id)

    if layout_ready_count >= len(refreshed) and layout_ready_count > 0:
        summary = f"全稿 {layout_ready_count} 页版式线框已就绪"
    elif applied > 0:
        summary = f"已生成 {applied} 页版式线框（{layout_ready_count}/{len(refreshed)}）"
    elif skipped > 0:
        summary = f"{layout_ready_count}/{len(refreshed)} 页版式线框已就绪"
    else:
        summary = "版式线框生成跳过（可稍后在生成页补做）"

    return GenesisDeckWireframeResult(
        applied_count=applied,
        skipped_count=skipped,
        failed_count=failed,
        layout_ready_count=layout_ready_count,
        cover_preview_path=cover_preview,
        summary=summary,
    )
