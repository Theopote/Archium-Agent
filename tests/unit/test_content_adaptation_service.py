"""Additional content adaptation coverage for critical service gate."""

from __future__ import annotations

import pytest

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(Project(name="Adaptation gate"))
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


def test_analyze_returns_suggestion_list(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    suggestions = service.analyze(slide.id)
    assert isinstance(suggestions, list)


def test_apply_shorten_updates_slide(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    before = len(slide.message)
    result = service.apply(slide.id, ContentAdaptationAction.SHORTEN, replan_visual=False)
    assert len(result.slide.message) <= before
    assert service.list_content_revisions(slide.id)


def test_apply_convert_to_bullets(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    result = service.apply(slide.id, ContentAdaptationAction.CONVERT_TO_BULLETS, replan_visual=False)
    assert result.slide.key_points
    assert len(result.slide.key_points) >= 1


def test_apply_promote_key_message(db_session: Session, slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    result = service.apply(slide.id, ContentAdaptationAction.PROMOTE_KEY_MESSAGE, replan_visual=False)
    assert result.slide.message
