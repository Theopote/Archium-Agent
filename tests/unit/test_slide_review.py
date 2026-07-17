"""Unit tests for slide review helpers."""

from __future__ import annotations

from archium.application.review_models import SlideUpdate
from archium.application.review_service import PresentationReviewService, slides_are_approved
from archium.domain.enums import ProjectType, SlideStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(
        Project(name="Slide 审核项目", project_type=ProjectType.HEALTHCARE)
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    PresentationRepository(db_session).save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="标题",
            audience="甲方",
            purpose="决策",
            core_message="核心",
        )
    )
    slide = SlideSpec(
        presentation_id=presentation.id,
        chapter_id="ch1",
        order=0,
        title="页面标题",
        message="页面核心观点。",
        slide_type=SlideType.CONTENT,
        status=SlideStatus.PLANNED,
    )
    return PresentationRepository(db_session).save_slide(slide)


def test_update_slide_resets_status_to_draft(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    service = PresentationReviewService(db_session)
    updated = service.update_slide(
        slide.id,
        SlideUpdate(
            chapter_id="ch1",
            order=0,
            title="新标题",
            message="新的核心观点。",
            slide_type=SlideType.CONTENT.value,
            key_points=["要点一"],
        ),
    )
    assert updated.title == "新标题"
    assert updated.status == SlideStatus.DRAFT


def test_approve_all_slides(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    service = PresentationReviewService(db_session)
    approved = service.approve_all_slides(slide.presentation_id)
    assert len(approved) == 1
    assert slides_are_approved(approved)
