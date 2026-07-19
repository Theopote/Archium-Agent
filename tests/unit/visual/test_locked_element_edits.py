"""Integration tests for locked element edit guards."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.enums import SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.element_lock import ElementLockedError
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import LayoutPlanRepository
from sqlalchemy.orm import Session


def _seed_slide_with_title_and_hero(db_session: Session) -> tuple[SlideSpec, LayoutPlan]:
    project = ProjectRepository(db_session).create(Project(name="Lock guard test"))
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
        reading_order=["title", "hero"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="原标题",
                x=1,
                y=0.5,
                width=8,
                height=0.8,
                locked=True,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref="assets/hero.png",
                x=1,
                y=1.5,
                width=8,
                height=3,
                locked=True,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    saved = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()
    return slide, saved


def test_locked_title_blocks_direct_text_update(db_session: Session) -> None:
    slide, _plan = _seed_slide_with_title_and_hero(db_session)
    service = VisualEditService(db_session)
    with pytest.raises(ElementLockedError, match="title"):
        service.apply_intent(
            slide.id,
            "update_element_text",
            params={"element_id": "title", "text": "新标题"},
        )


def test_locked_hero_blocks_direct_asset_update(db_session: Session) -> None:
    slide, _plan = _seed_slide_with_title_and_hero(db_session)
    service = VisualEditService(db_session)
    with pytest.raises(ElementLockedError, match="hero"):
        service.apply_intent(
            slide.id,
            "set_element_asset",
            params={"element_id": "hero", "content_ref": "assets/new.png"},
        )


def test_locked_hero_blocks_set_hero_asset_replan(db_session: Session) -> None:
    slide, _plan = _seed_slide_with_title_and_hero(db_session)
    service = VisualEditService(db_session)
    with pytest.raises(ElementLockedError, match="hero"):
        service.apply_intent(
            slide.id,
            "set_hero_asset",
            params={"asset_id": str(uuid4())},
        )


def test_unlock_allows_text_update(db_session: Session) -> None:
    slide, _plan = _seed_slide_with_title_and_hero(db_session)
    service = VisualEditService(db_session)
    service.apply_intent(slide.id, "unlock_element", params={"element_id": "title"})
    result = service.apply_intent(
        slide.id,
        "update_element_text",
        params={"element_id": "title", "text": "新标题"},
    )
    assert result.layout_plan is not None
    title = result.layout_plan.element_by_id("title")
    assert title is not None
    assert title.text_content == "新标题"
