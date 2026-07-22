"""Unit tests for OutlineApprovalService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from archium.application.outline_approval_service import OutlineApprovalService
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)


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
    )
    saved = presentations.save_outline(outline)
    presentation.current_outline_id = saved.id
    presentations.update_presentation(presentation)
    session.commit()
    return project, presentation, saved


def test_approve_persists_outline_status(db_session: Session) -> None:
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
    refreshed = PresentationRepository(db_session).get_outline(outline.id)
    assert refreshed is not None
    assert refreshed.approval_status == ApprovalStatus.APPROVED


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
