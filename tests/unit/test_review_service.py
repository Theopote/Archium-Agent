"""Unit tests for presentation review service."""

from __future__ import annotations

from uuid import uuid4

from archium.application.review_models import BriefUpdate, ChapterUpdate, StorylineUpdate
from archium.application.review_service import (
    PresentationReviewService,
    _manuscript_from_workflow_state,
    _select_review_workflow_run,
)
from archium.domain.enums import (
    ApprovalStatus,
    ProjectType,
    ReviewCategory,
    ReviewSeverity,
    WorkflowStatus,
)
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
    WorkflowRunRepository,
)
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
        rule_code=ReviewRuleCode.LEGACY_UNSPECIFIED,
        title="测试问题",
        description="描述",
    )

    stored = ReviewRepository(db_session).create(issue)
    service = PresentationReviewService(db_session)

    resolved = service.resolve_review_issue(stored.id)
    assert resolved.status.value == "resolved"

    issue2 = ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=brief.presentation_id,
            category=ReviewCategory.VISUAL,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LEGACY_UNSPECIFIED,
            title="视觉问题",
            description="描述",
        )
    )
    dismissed = service.dismiss_review_issue(issue2.id)
    assert dismissed.status.value == "dismissed"


def test_list_review_issues_by_project(db_session: Session) -> None:

    brief = _seed_brief(db_session)
    project_id = brief.project_id
    presentation_two = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="第二版汇报")
    )
    ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=brief.presentation_id,
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
            title="缺少引用来源",
            description="第一版",
        )
    )
    ReviewRepository(db_session).create(
        ReviewIssue(
            presentation_id=presentation_two.id,
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
            title="要点过多",
            description="第二版",
        )
    )

    service = PresentationReviewService(db_session)
    project_issues = service.list_review_issues_by_project(project_id)

    assert len(project_issues) == 2
    rule_codes = {issue.rule_code for issue in project_issues}
    assert ReviewRuleCode.EVIDENCE_MISSING_CITATION in rule_codes
    assert ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS in rule_codes


def test_select_review_workflow_run_prefers_non_visual() -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    visual = WorkflowRun(
        project_id=project_id,
        presentation_id=presentation_id,
        status=WorkflowStatus.AWAITING_REVIEW,
        state={"workflow_kind": "visual_composition", "presentation": None},
    )
    narrative = WorkflowRun(
        project_id=project_id,
        presentation_id=presentation_id,
        status=WorkflowStatus.AWAITING_REVIEW,
        state={"manuscript": {"id": str(uuid4())}},
    )
    selected = _select_review_workflow_run([visual, narrative])
    assert selected is narrative


def test_manuscript_from_visual_workflow_state_is_none(db_session: Session) -> None:
    assert (
        _manuscript_from_workflow_state(
            db_session,
            {"workflow_kind": "visual_composition", "presentation": None},
        )
        is None
    )


def test_get_review_context_tolerates_visual_null_presentation(db_session: Session) -> None:
    brief = _seed_brief(db_session)
    presentation_id = brief.presentation_id
    WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=brief.project_id,
            presentation_id=presentation_id,
            status=WorkflowStatus.AWAITING_REVIEW,
            state={
                "workflow_kind": "visual_composition",
                "presentation": None,
                "brief": None,
                "manuscript": None,
            },
        )
    )
    context = PresentationReviewService(db_session).get_review_context(presentation_id)
    assert context is not None
    assert context.presentation.id == presentation_id
    assert context.workflow_run is not None
    assert context.workflow_run.state.get("presentation") is None
