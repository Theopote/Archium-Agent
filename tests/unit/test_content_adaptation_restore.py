"""Unit tests for content adaptation undo."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository


@pytest.fixture
def slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(Project(name="Undo test"))
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
            message="本页核心结论：需要通过拆页验证内容撤销。",
            key_points=[
                "第一点说明现状问题与改造背景。",
                "第二点说明设计策略与空间组织。",
                "第三点说明实施路径与分期计划。",
            ],
            slide_type=SlideType.CONTENT,
        )
    )
    db_session.commit()
    return slide


def test_restore_previous_reverts_content_adaptation(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    original_points = list(slide.key_points)
    service.apply(slide.id, ContentAdaptationAction.SPLIT_SLIDE, replan_visual=False)
    updated = PresentationRepository(db_session).get_slide(slide.id)
    assert updated is not None
    assert updated.key_points != original_points

    restored = service.restore_previous(slide.id, replan_visual=False)
    assert restored.slide.key_points == original_points


def test_restore_previous_without_history_raises(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    with pytest.raises(WorkflowError, match="没有可撤销"):
        service.restore_previous(slide.id, replan_visual=False)
