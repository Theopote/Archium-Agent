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
    SlideRepairTier,
    SlideStatus,
    SlideType,
)
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_presentation_responses import SLIDE_REPAIR_JSON
from tests.unit.test_slide_repair_policy import _TIER4_LONG_MESSAGE


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
            rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
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

    slides, repaired, records = SlideRepairService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, slide_repair_enabled=False, llm_api_key="test"),
    ).repair_slides(presentation_id, [slide], [issue])

    assert repaired == 0
    assert records == []
    assert len(mock_llm.calls) == 0
    assert slides[0].title == "旧标题"


def test_rule_repair_trims_layout_issues_without_llm(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="规则修复项目"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="规则修复")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="综合结论",
            message="这是一段较长的核心结论用于测试版面密度" * 12,
            slide_type=SlideType.CONTENT,
            key_points=[f"要点描述内容 {index}" * 4 for index in range(5)],
            status=SlideStatus.PLANNED,
        )
    )
    issue = ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=slide.id,
            category=ReviewCategory.LENGTH,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
            title="页面信息密度过高",
            description="文本量过高",
            auto_fixable=True,
        )
    )

    slides, repaired, records = SlideRepairService(
        db_session,
        llm=None,
        settings=Settings(_env_file=None, slide_repair_enabled=False),
    ).repair_slides(presentation.id, [slide], [issue])

    assert repaired == 1
    assert len(slides[0].key_points) >= 1
    assert records
    assert records[0].tier in {
        SlideRepairTier.SHORTEN_REPETITION,
        SlideRepairTier.REWRITE,
        SlideRepairTier.SPLIT,
    }
    assert records[0].before_message != records[0].after_message or records[0].split_slide_id

    refreshed_issue = ReviewRepository(db_session).get_by_id(issue.id)
    assert refreshed_issue is not None
    assert refreshed_issue.status == ReviewStatus.RESOLVED


def test_rule_repair_defers_when_protected_numbers_cannot_be_trimmed(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="受保护修复项目"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="受保护修复")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="床位规模",
            message=_TIER4_LONG_MESSAGE,
            slide_type=SlideType.CONTENT,
            key_points=["需确认分期策略"],
            status=SlideStatus.PLANNED,
        )
    )
    issue = ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=slide.id,
            category=ReviewCategory.LENGTH,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
            title="页面信息密度过高",
            description="文本量过高",
            auto_fixable=True,
        )
    )

    slides, repaired, records = SlideRepairService(
        db_session,
        llm=None,
        settings=Settings(_env_file=None, slide_repair_enabled=False),
    ).repair_slides(presentation.id, [slide], [issue])

    assert repaired == 0
    assert records
    assert records[0].requires_manual_confirmation
    assert records[0].tier == SlideRepairTier.USER_CONFIRMATION
    assert "500" in slides[0].message

    pending = ReviewRepository(db_session).list_by_presentation(presentation.id)
    manual = [item for item in pending if item.title == "需人工确认版面调整"]
    assert manual

    refreshed_issue = ReviewRepository(db_session).get_by_id(issue.id)
    assert refreshed_issue is not None
    assert refreshed_issue.status == ReviewStatus.OPEN


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

    slides, repaired, records = SlideRepairService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, slide_repair_enabled=True, llm_api_key="test"),
    ).repair_slides(presentation_id, [slide], [issue], brief=brief)

    assert repaired == 1
    assert slides[0].title == "交通现状"
    assert "交通组织" in slides[0].message
    assert len(slides[0].key_points) == 2
    assert records
    assert records[0].before_message == "旧信息"

    refreshed_issue = ReviewRepository(db_session).get_by_id(issue.id)
    assert refreshed_issue is not None
    assert refreshed_issue.status == ReviewStatus.RESOLVED
    assert len(mock_llm.calls) == 1
