"""Unit tests for lock/unlock element visual edits."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.enums import RevisionSource, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from sqlalchemy.orm import Session


def _seed_slide_with_plan(db_session: Session) -> tuple[SlideSpec, LayoutPlan]:
    project = ProjectRepository(db_session).create(Project(name="Lock test"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="Page",
            message="Msg",
            slide_type=SlideType.CONTENT,
        )
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero",
        reading_order=["hero"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=8,
                height=3,
                locked=False,
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    from archium.infrastructure.database.visual_repositories import LayoutPlanRepository

    saved = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()
    return slide, saved


def test_unlock_element_clears_locked_flag(db_session: Session) -> None:
    slide, plan = _seed_slide_with_plan(db_session)
    locked_plan = plan.model_copy(
        update={
            "elements": [plan.elements[0].model_copy(update={"locked": True})],
            "version": plan.version + 1,
        }
    )
    from archium.infrastructure.database.visual_repositories import LayoutPlanRepository

    LayoutPlanRepository(db_session).save(locked_plan)
    slide.layout_plan_id = locked_plan.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()

    service = VisualEditService(db_session)
    result = service.apply_intent(
        slide.id,
        "unlock_element",
        params={"element_id": "hero"},
    )
    assert result.layout_plan is not None
    assert result.layout_plan.elements[0].locked is False
