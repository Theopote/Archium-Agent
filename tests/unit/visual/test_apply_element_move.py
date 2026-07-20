"""Unit tests for canvas drag move API."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import LayoutPlanRepository
from sqlalchemy.orm import Session


@pytest.fixture
def slide_with_plan(db_session: Session) -> tuple[SlideSpec, LayoutPlan]:
    project = ProjectRepository(db_session).create(Project(name="Move Test"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Move Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Move Deck",
            audience="甲方",
            purpose="测试",
            core_message="核心信息。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="测试页",
            message="核心信息。",
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
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                x=1,
                y=0.5,
                width=8,
                height=0.5,
                text_content="标题",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=4,
                height=2,
            ),
            LayoutElement(
                id="caption",
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=1,
                y=3.5,
                width=4,
                height=0.5,
                text_content="说明",
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    saved_plan = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved_plan.id
    presentations.save_slide(slide)
    db_session.commit()
    return slide, saved_plan


def test_apply_element_move_updates_geometry(
    db_session: Session,
    slide_with_plan: tuple[SlideSpec, LayoutPlan],
) -> None:
    slide, plan = slide_with_plan
    service = VisualEditService(db_session)
    result = service.apply_element_move(slide.id, "caption", x=1.5, y=3.6)
    assert result.layout_plan is not None
    moved = result.layout_plan.element_by_id("caption")
    assert moved is not None
    assert moved.x == pytest.approx(1.5)
    assert moved.y == pytest.approx(3.6)


def test_apply_element_move_rejects_locked_element(
    db_session: Session,
    slide_with_plan: tuple[SlideSpec, LayoutPlan],
) -> None:
    slide, plan = slide_with_plan
    locked_plan = plan.model_copy(
        update={
            "elements": [
                element.model_copy(update={"locked": element.id == "caption"})
                for element in plan.elements
            ],
            "version": plan.version + 1,
        }
    )
    locked_plan.touch()
    LayoutPlanRepository(db_session).save(locked_plan)
    slide.layout_plan_id = locked_plan.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()

    service = VisualEditService(db_session)
    with pytest.raises(WorkflowError):
        service.apply_element_move(slide.id, "caption", x=8.0, y=4.5)


def test_restore_previous_after_move_returns_prior_position(
    db_session: Session,
    slide_with_plan: tuple[SlideSpec, LayoutPlan],
) -> None:
    slide, plan = slide_with_plan
    service = VisualEditService(db_session)
    before = plan.element_by_id("caption")
    assert before is not None
    service.apply_element_move(slide.id, "caption", x=1.5, y=3.6)
    restored = service.restore_previous(slide.id)
    assert restored.layout_plan is not None
    caption = restored.layout_plan.element_by_id("caption")
    assert caption is not None
    assert caption.x == pytest.approx(before.x)
    assert caption.y == pytest.approx(before.y)
