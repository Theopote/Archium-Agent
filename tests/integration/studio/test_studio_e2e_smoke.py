"""Integration smoke test for Presentation Studio service chain."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.ui.studio_service import (
    apply_slide_edit_command,
    count_visual_revisions,
    reorder_studio_slide,
)


@pytest.fixture
def studio_seed(db_session: Session) -> tuple[Presentation, SlideSpec]:
    project = ProjectRepository(db_session).create(Project(name="Studio E2E"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Studio Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Studio Deck",
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
            title="封面",
            message="本页核心结论：Studio 集成测试验证内容适配；第二句说明空间策略；第三句说明实施路径。",
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
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    from archium.infrastructure.database.visual_repositories import LayoutPlanRepository

    saved_plan = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved_plan.id
    presentations.save_slide(slide)
    db_session.commit()
    return presentation, slide


def test_studio_service_chain_smoke(db_session: Session, studio_seed) -> None:
    presentation, slide = studio_seed
    second = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=1,
            title="第二页",
            message="第二页信息",
            slide_type=SlideType.CONTENT,
        )
    )
    db_session.commit()

    reorder_studio_slide(db_session, presentation.id, from_index=1, to_index=0)
    slides = PresentationRepository(db_session).list_slides(presentation.id)
    assert slides[0].id == second.id

    command = SlideEditCommand(
        slide_id=slide.id,
        scope=SlideEditScope.VISUAL,
        action=VisualEditIntent.LOCK_ELEMENT.value,
        params={"element_id": "hero"},
    )
    apply_slide_edit_command(db_session, command)

    content = ContentAdaptationService(db_session)
    original = PresentationRepository(db_session).get_slide(slide.id)
    assert original is not None
    original_points = list(original.key_points)
    content.apply(slide.id, ContentAdaptationAction.CONVERT_TO_BULLETS, replan_visual=False)
    changed = PresentationRepository(db_session).get_slide(slide.id)
    assert changed is not None
    assert changed.key_points != original.key_points or changed.message != original.message
    content.restore_previous(slide.id, replan_visual=False)
    restored = PresentationRepository(db_session).get_slide(slide.id)
    assert restored is not None
    assert restored.key_points == original.key_points

    visual = VisualEditService(db_session)
    visual.apply_intent(slide.id, VisualEditIntent.INCREASE_WHITESPACE)
    first_restore = visual.restore_previous(slide.id)
    assert first_restore.restored is True
    assert count_visual_revisions(db_session, slide.id) >= 1
