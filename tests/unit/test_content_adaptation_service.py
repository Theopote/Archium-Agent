"""Integration tests for content adaptation service."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.content_adaptation_service import ContentAdaptationService
from archium.domain.citation import Citation
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def dense_slide(db_session: Session) -> SlideSpec:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="内容适配测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="内容汇报")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="内容汇报",
            audience="甲方",
            purpose="测试",
            core_message="核心信息。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="测试论点。",
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
            title="现状分析",
            message="院区车行组织混乱，落客区与消防通道冲突，高峰期拥堵严重。",
            slide_type=SlideType.CONTENT,
            key_points=[
                "落客区与消防通道冲突",
                "高峰期拥堵严重",
                "人行与车行混行",
                "需优化交通组织",
            ],
            visual_requirements=[
                VisualRequirement(type=VisualType.SITE_PLAN, description="总平面")
            ],
            source_citations=[
                Citation(document_id=uuid4(), document_name="任务书.pdf", page_number=1)
            ],
        )
    )
    db_session.commit()
    return slide


def test_shorten_updates_slide(db_session: Session, dense_slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    result = service.apply(dense_slide.id, ContentAdaptationAction.SHORTEN, replan_visual=False)
    assert len(result.slide.message) <= len(dense_slide.message)


def test_convert_to_bullets(db_session: Session) -> None:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="要点测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="要点汇报")
    )
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="策略",
            message="优化落客组织，分离人行与车行，增设地面标识。",
            slide_type=SlideType.CONTENT,
        )
    )
    db_session.commit()
    service = ContentAdaptationService(db_session)
    result = service.apply(slide.id, ContentAdaptationAction.CONVERT_TO_BULLETS, replan_visual=False)
    assert len(result.slide.key_points) >= 2


def test_split_slide_creates_continuation(db_session: Session, dense_slide: SlideSpec) -> None:
    service = ContentAdaptationService(db_session)
    result = service.apply(dense_slide.id, ContentAdaptationAction.SPLIT_SLIDE, replan_visual=False)
    assert len(result.created_slides) == 1
    assert result.created_slides[0].order == dense_slide.order + 1
