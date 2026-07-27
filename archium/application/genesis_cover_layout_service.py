"""Generate cover slide wireframe layout after genesis starter draft."""

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
from archium.domain.visual.defaults import default_presentation_design_system
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenesisCoverLayoutResult:
    applied: bool
    slide_id: UUID | None
    layout_plan_id: UUID | None
    preview_path: str | None
    summary: str


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


def ensure_cover_wireframe_layout(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings | None = None,
) -> GenesisCoverLayoutResult:
    """Rule-based VisualIntent + LayoutPlan + wireframe PNG for the cover slide."""
    resolved = settings or get_settings()
    presentations = PresentationRepository(session)
    slides = sorted(
        presentations.list_slides(presentation_id),
        key=lambda item: item.order,
    )
    if not slides:
        return GenesisCoverLayoutResult(
            applied=False,
            slide_id=None,
            layout_plan_id=None,
            preview_path=None,
            summary="尚无封面页，跳过版式生成",
        )

    slide = slides[0]
    plans = LayoutPlanRepository(session)
    preview_service = SlidePreviewService(resolved)

    if slide.layout_plan_id is not None:
        plan = plans.get(slide.layout_plan_id)
        if plan is not None:
            wireframe = preview_service._ensure_wireframe_preview(presentation_id, plan)
            if wireframe is not None and wireframe.is_file():
                return GenesisCoverLayoutResult(
                    applied=False,
                    slide_id=slide.id,
                    layout_plan_id=plan.id,
                    preview_path=str(wireframe),
                    summary="封面版式线框已就绪",
                )

    design_repo = DesignSystemRepository(session)
    design = design_repo.get(default_presentation_design_system().id)
    if design is None:
        design = design_repo.save(default_presentation_design_system())

    try:
        intent_service = VisualIntentService(session, llm=None, settings=resolved)
        intent = intent_service.generate_for_slide(slide, use_llm=False)
        intent = VisualIntentRepository(session).save(intent)
        slide.visual_intent_id = intent.id
        presentations.save_slide(slide)

        planner = LayoutPlanningService(session, llm=None, settings=resolved)
        plan = planner.plan_slide(
            slide=slide,
            visual_intent_id=intent.id,
            art_direction_id=intent.art_direction_id,
            design_system_id=design.id,
            candidate_count=1,
            project_id=project_id,
        )
        slide.layout_plan_id = plan.id
        presentations.save_slide(slide)

        LayoutValidationService().validate(plan, design)

        wireframe = preview_service._ensure_wireframe_preview(presentation_id, plan)
        preview_path = str(wireframe) if wireframe is not None and wireframe.is_file() else None
        session.commit()
        return GenesisCoverLayoutResult(
            applied=True,
            slide_id=slide.id,
            layout_plan_id=plan.id,
            preview_path=preview_path,
            summary="封面版式线框已生成，可在工作室预览",
        )
    except Exception as exc:
        logger.exception(
            "Genesis cover wireframe failed for presentation %s: %s",
            presentation_id,
            exc,
        )
        session.rollback()
        return GenesisCoverLayoutResult(
            applied=False,
            slide_id=slide.id,
            layout_plan_id=None,
            preview_path=None,
            summary="封面线框生成跳过（可稍后在生成页补做）",
        )
