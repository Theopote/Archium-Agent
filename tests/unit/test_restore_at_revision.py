"""Unit tests for restore-at-revision APIs."""

from __future__ import annotations

from uuid import uuid4

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.application.visual.visual_edit_service import VisualEditService
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(Project(name="RestoreAt"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Deck",
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
            title="页面",
            message="本页核心结论：需要通过拆页验证按 revision 恢复。",
            key_points=["第一点说明现状。", "第二点说明策略。", "第三点说明路径。"],
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

    saved = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved.id
    presentations.save_slide(slide)
    db_session.commit()
    return slide


def test_content_restore_at_revision(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    service = ContentAdaptationService(db_session)
    original_points = list(slide.key_points)
    service.apply(slide.id, ContentAdaptationAction.SPLIT_SLIDE, replan_visual=False)
    revisions = service.list_content_revisions(slide.id)
    assert revisions
    target = revisions[-1]
    restored = service.restore_at_revision(slide.id, target.id, replan_visual=False)
    assert restored.slide.key_points == original_points


def test_visual_restore_at_revision(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    visual = VisualEditService(db_session)
    before = visual.apply_intent(slide.id, VisualEditIntent.INCREASE_WHITESPACE)
    assert before.layout_plan is not None
    refreshed = PresentationRepository(db_session).get_slide(slide.id)
    assert refreshed is not None
    revisions = VisualHistoryService(db_session).list_slide_visual_revisions(refreshed)
    assert revisions
    target = revisions[-1]
    restored = visual.restore_at_revision(slide.id, target.id)
    assert restored.restored is True
    assert restored.layout_plan is not None
