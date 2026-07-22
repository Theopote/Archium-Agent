"""Unit tests for OutlineApprovalService."""

from __future__ import annotations

import pytest
from archium.application.outline_approval_service import OutlineApprovalService
from archium.application.review_models import (
    OutlineSectionUpdate,
    OutlineUpdate,
    SlideIntentUpdate,
)
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide_intent import SlideIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    OutlineApprovalRecordRepository,
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _seed_outline(session: Session) -> tuple[Project, Presentation, OutlinePlan]:
    project = ProjectRepository(session).create(Project(name="审批测试"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    outline = OutlinePlan(
        presentation_id=presentation.id,
        title="测试大纲",
        thesis="核心论点",
        audience="院领导",
        purpose="确认方案",
        target_slide_count=12,
        audience_mode=OutlineAudienceMode.GOVERNMENT,
        sections=[
            OutlineSection(
                id="s1",
                title="现状",
                purpose="说明问题",
                key_message="现状紧张",
                order=0,
            )
        ],
        page_intents=[
            SlideIntent(
                order=0,
                page_task="说明现状",
                central_conclusion="问题明确",
            )
        ],
    )
    saved = presentations.save_outline(outline)
    presentation.current_outline_id = saved.id
    presentations.update_presentation(presentation)
    session.commit()
    return project, presentation, saved


def test_approve_persists_outline_status_and_audit_row(db_session: Session) -> None:
    project, _presentation, outline = _seed_outline(db_session)
    assert outline.approval_status == ApprovalStatus.DRAFT

    result = OutlineApprovalService(db_session).approve_for_project(
        project.id,
        approved_by="tester",
        expected_revision=outline.version,
    )
    db_session.commit()

    assert result.approval_status == ApprovalStatus.APPROVED.value
    assert result.approved_revision == outline.version
    assert result.outline_hash
    assert result.approval_record_id is not None
    refreshed = PresentationRepository(db_session).get_outline(outline.id)
    assert refreshed is not None
    assert refreshed.approval_status == ApprovalStatus.APPROVED

    rows = OutlineApprovalRecordRepository(db_session).list_by_outline(outline.id)
    assert len(rows) == 1
    assert rows[0].approved_by == "tester"
    assert rows[0].outline_hash == result.outline_hash
    assert rows[0].outline_revision == outline.version
    assert rows[0].is_active


def test_edit_after_approve_supersedes_audit_row(db_session: Session) -> None:
    project, _presentation, outline = _seed_outline(db_session)
    OutlineApprovalService(db_session).approve_for_project(
        project.id,
        approved_by="tester",
        expected_revision=outline.version,
    )
    db_session.commit()

    approved = PresentationRepository(db_session).get_outline(outline.id)
    assert approved is not None
    PresentationReviewService(db_session).update_outline(
        approved.id,
        OutlineUpdate(
            title=approved.title,
            thesis=approved.thesis,
            audience=approved.audience,
            purpose=approved.purpose,
            target_slide_count=approved.target_slide_count,
            audience_mode=approved.audience_mode.value,
            sections=[
                OutlineSectionUpdate(
                    id=s.id,
                    title=s.title,
                    purpose=s.purpose,
                    key_message=s.key_message,
                    order=s.order,
                    estimated_slide_count=s.estimated_slide_count,
                    evidence_requirements=list(s.evidence_requirements),
                    required_assets=list(s.required_assets),
                    required=s.required,
                    expanded=s.expanded,
                    category=s.category,
                )
                for s in approved.sections
            ],
            page_intents=[
                SlideIntentUpdate(
                    order=0,
                    page_task="修订后的页面任务",
                    central_conclusion="新结论",
                )
            ],
            expected_version=approved.version,
        ),
    )
    db_session.commit()

    rows = OutlineApprovalRecordRepository(db_session).list_by_outline(outline.id)
    assert len(rows) == 1
    assert rows[0].superseded_at is not None
    assert not rows[0].is_active


def test_update_outline_rejects_stale_expected_version(db_session: Session) -> None:
    _project, _presentation, outline = _seed_outline(db_session)
    with pytest.raises(WorkflowError, match="版本冲突"):
        PresentationReviewService(db_session).update_outline(
            outline.id,
            OutlineUpdate(
                title=outline.title,
                thesis=outline.thesis,
                audience=outline.audience,
                purpose=outline.purpose,
                target_slide_count=outline.target_slide_count,
                audience_mode=outline.audience_mode.value,
                sections=[],
                page_intents=[],
                expected_version=outline.version + 5,
            ),
        )


def test_approve_rejects_incomplete_outline(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="不完整大纲"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="空结构")
    )
    outline = OutlinePlan(
        presentation_id=presentation.id,
        title="空",
        thesis="论点",
        audience="院领导",
        purpose="确认",
        target_slide_count=8,
        sections=[],
        page_intents=[],
    )
    saved = presentations.save_outline(outline)
    presentation.current_outline_id = saved.id
    presentations.update_presentation(presentation)
    db_session.commit()

    with pytest.raises(WorkflowError, match="尚未就绪"):
        OutlineApprovalService(db_session).approve_for_project(project.id)


def test_approve_rejects_stale_revision(db_session: Session) -> None:
    project, _presentation, outline = _seed_outline(db_session)
    with pytest.raises(WorkflowError, match="版本已变更"):
        OutlineApprovalService(db_session).approve_for_project(
            project.id,
            expected_revision=outline.version + 1,
        )


def test_approve_without_presentation_raises(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="空项目"))
    db_session.commit()
    with pytest.raises(WorkflowError, match="尚无汇报"):
        OutlineApprovalService(db_session).approve_for_project(project.id)


def test_approve_without_outline_plan_raises(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="仅有汇报"))
    PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="无大纲")
    )
    db_session.commit()
    with pytest.raises(WorkflowError, match="尚无 OutlinePlan"):
        OutlineApprovalService(db_session).approve_for_project(project.id)
