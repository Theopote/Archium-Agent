"""Unit tests for SlideRepairService."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from archium.application.slide_repair_service import SlideRepairService
from archium.config.settings import Settings
from archium.domain.enums import (
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    SlideStatus,
    SlideType,
)
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_presentation_responses import SLIDE_REPAIR_JSON


def _slide_repair_selector(request: LLMRequest) -> str | None:
    if "修订以下页面 JSON" in request.user_prompt:
        return SLIDE_REPAIR_JSON
    return None


@pytest.fixture
def presentation_context(db_session: Session) -> tuple[UUID, SlideSpec, ReviewIssue]:
    project = ProjectRepository(db_session).create(Project(name="修复测试项目"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="修复测试")
    )
    slide = SlideSpec(
        presentation_id=presentation.id,
        chapter_id="ch1",
        order=0,
        title="旧标题",
        message="旧信息",
        slide_type=SlideType.CONTENT,
        status=SlideStatus.PLANNED,
    )
    saved_slide = PresentationRepository(db_session).save_slide(slide)
    issue = ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=saved_slide.id,
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.CRITICAL,
            title="缺少核心信息",
            description="第 1 页缺少核心结论。",
        )
    )
    return presentation.id, saved_slide, issue


def test_repair_disabled_is_noop(
    db_session: Session,
    presentation_context: tuple[UUID, SlideSpec, ReviewIssue],
) -> None:
    presentation_id, slide, issue = presentation_context
    mock_llm = MockLLMProvider(selector=_slide_repair_selector)

    slides, repaired = SlideRepairService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, slide_repair_enabled=False, llm_api_key="test"),
    ).repair_slides(presentation_id, [slide], [issue])

    assert repaired == 0
    assert len(mock_llm.calls) == 0


def test_repair_updates_slide_and_resolves_issue(
    db_session: Session,
    presentation_context: tuple[UUID, SlideSpec, ReviewIssue],
) -> None:
    presentation_id, slide, issue = presentation_context
    mock_llm = MockLLMProvider(selector=_slide_repair_selector)
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="测试汇报",
        audience="管理层",
        purpose="确认方向",
        core_message="改善交通组织",
    )

    slides, repaired = SlideRepairService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, slide_repair_enabled=True, llm_api_key="test"),
    ).repair_slides(presentation_id, [slide], [issue], brief=brief)

    assert repaired == 1
    assert slides[0].title == "交通现状"
    assert "交通组织" in slides[0].message
    assert len(slides[0].key_points) == 2

    refreshed_issue = ReviewRepository(db_session).get_by_id(issue.id)
    assert refreshed_issue is not None
    assert refreshed_issue.status == ReviewStatus.RESOLVED
    assert len(mock_llm.calls) == 1
