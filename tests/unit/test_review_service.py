"""Unit tests for presentation review service."""

from __future__ import annotations

from archium.application.review_models import BriefUpdate, ChapterUpdate, StorylineUpdate
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ApprovalStatus, ProjectType, ReviewCategory, ReviewSeverity
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_brief(db_session: Session) -> PresentationBrief:
    project = ProjectRepository(db_session).create(
        Project(name="审核测试项目", project_type=ProjectType.HEALTHCARE)
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    brief = PresentationBrief(
        project_id=project.id,
        presentation_id=presentation.id,
        title="初稿标题",
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
        approval_status=ApprovalStatus.PENDING,
    )
    return PresentationRepository(db_session).save_brief(brief)


def _seed_storyline(db_session: Session, brief: PresentationBrief) -> Storyline:
    storyline = Storyline(
        presentation_id=brief.presentation_id,
        thesis="初始论点",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="痛点",
                order=0,
            )
        ],
        approval_status=ApprovalStatus.PENDING,
    )
    return PresentationRepository(db_session).save_storyline(storyline)


def test_update_brief_resets_approval_to_draft(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    service = PresentationReviewService(db_session)
    updated = service.update_brief(
        brief.id,
        BriefUpdate(
            title="修订标题",
            audience="管理层",
            purpose="确认方向",
            core_message="更新后的核心信息",
            required_sections=["现状分析"],
        ),
    )
    assert updated.title == "修订标题"
    assert updated.approval_status == ApprovalStatus.DRAFT


def test_approve_brief(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    service = PresentationReviewService(db_session)
    approved = service.approve_brief(brief.id)
    assert approved.approval_status == ApprovalStatus.APPROVED


def test_update_storyline_chapters(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    storyline = _seed_storyline(db_session, brief)
    service = PresentationReviewService(db_session)
    updated = service.update_storyline(
        storyline.id,
        StorylineUpdate(
            thesis="修订论点",
            chapters=[
                ChapterUpdate(
                    id="ch1",
                    title="现状分析",
                    purpose="说明问题",
                    key_message="交通混乱",
                    order=0,
                    estimated_slide_count=2,
                )
            ],
        ),
    )
    assert updated.thesis == "修订论点"
    assert updated.chapters[0].title == "现状分析"
    assert updated.approval_status == ApprovalStatus.DRAFT


def test_resolve_and_dismiss_review_issue(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    issue = ReviewIssue(
        presentation_id=brief.presentation_id,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.CRITICAL,
        title="测试问题",
        description="描述",
    )
    from archium.infrastructure.database.repositories import ReviewRepository

    stored = ReviewRepository(db_session).create(issue)
    service = PresentationReviewService(db_session)

    resolved = service.resolve_review_issue(stored.id)
    assert resolved.status.value == "resolved"

    issue2 = ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=brief.presentation_id,
            category=ReviewCategory.VISUAL,
            severity=ReviewSeverity.MEDIUM,
            title="视觉问题",
            description="描述",
        )
    )
    dismissed = service.dismiss_review_issue(issue2.id)
    assert dismissed.status.value == "dismissed"
