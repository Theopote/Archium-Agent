"""Unit tests for direct element text edits."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.enums import SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_text_element(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(Project(name="Text edit"))
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
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="stack",
        page_width=10,
        page_height=5.625,
        hero_element_id=None,
        reading_order=["body"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="旧文字",
                x=1,
                y=1,
                width=8,
                height=2,
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
    return slide


def test_update_element_text_patches_layout_plan(db_session: Session) -> None:
    slide = _seed_text_element(db_session)
    service = VisualEditService(db_session)
    result = service.apply_intent(
        slide.id,
        "update_element_text",
        params={"element_id": "body", "text": "新文字内容"},
    )
    assert result.layout_plan is not None
    assert result.layout_plan.elements[0].text_content == "新文字内容"
