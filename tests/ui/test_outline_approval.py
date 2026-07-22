"""Outline approval persistence and re-confirm after edits."""

from __future__ import annotations

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
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _seed(session: Session) -> tuple[Project, Presentation, OutlinePlan]:
    project = ProjectRepository(session).create(Project(name="大纲确认 UI"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="确认测试")
    )
    outline = OutlinePlan(
        presentation_id=presentation.id,
        title="测试大纲",
        thesis="核心论点",
        audience="院领导",
        purpose="确认方案",
        target_slide_count=8,
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
                notes="第 1 页",
            )
        ],
    )
    saved = presentations.save_outline(outline)
    presentation.current_outline_id = saved.id
    presentations.update_presentation(presentation)
    session.commit()
    return project, presentation, saved


def _outline_update(outline: OutlinePlan, *, intents: list[SlideIntentUpdate]) -> OutlineUpdate:
    return OutlineUpdate(
        title=outline.title,
        thesis=outline.thesis,
        audience=outline.audience,
        purpose=outline.purpose,
        target_slide_count=outline.target_slide_count,
        audience_mode=outline.audience_mode.value,
        sections=[
            OutlineSectionUpdate(
                id=section.id,
                title=section.title,
                purpose=section.purpose,
                key_message=section.key_message,
                order=section.order,
                estimated_slide_count=section.estimated_slide_count,
                evidence_requirements=list(section.evidence_requirements),
                required_assets=list(section.required_assets),
                required=section.required,
                expanded=section.expanded,
                category=section.category,
            )
            for section in outline.sections
        ],
        page_intents=intents,
        page_asset_bindings=[],
        expected_version=outline.version,
    )


def test_confirm_outline_sets_approved(db_session: Session) -> None:
    project, _presentation, outline = _seed(db_session)
    result = OutlineApprovalService(db_session).approve_for_project(
        project.id,
        approved_by="tester",
        expected_revision=outline.version,
    )
    db_session.commit()
    assert result.approval_status == ApprovalStatus.APPROVED.value
    refreshed = PresentationRepository(db_session).get_outline(outline.id)
    assert refreshed is not None
    assert refreshed.approval_status == ApprovalStatus.APPROVED


def test_edit_after_approve_sets_changes_pending(db_session: Session) -> None:
    project, _presentation, outline = _seed(db_session)
    OutlineApprovalService(db_session).approve_for_project(
        project.id,
        approved_by="tester",
        expected_revision=outline.version,
    )
    db_session.commit()

    approved = PresentationRepository(db_session).get_outline(outline.id)
    assert approved is not None
    assert approved.approval_status == ApprovalStatus.APPROVED

    intents = [
        SlideIntentUpdate(
            order=0,
            page_task="修改后的页面任务",
            central_conclusion="新的中心结论",
            notes="第 1 页修订",
        )
    ]
    PresentationReviewService(db_session).update_outline(
        approved.id,
        _outline_update(approved, intents=intents),
    )
    db_session.commit()

    revised = PresentationRepository(db_session).get_outline(outline.id)
    assert revised is not None
    assert revised.approval_status == ApprovalStatus.CHANGES_PENDING
    assert revised.page_intents[0].page_task == "修改后的页面任务"
    assert not revised.is_approved


def test_outline_page_has_no_bypass_generate_link() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "outline.py"
    ).read_text(encoding="utf-8")
    assert "直接前往生成" not in text
    assert "include_next=False" in text
    assert "OutlineApprovalService" in text
    assert "确认大纲并开始生成" in text
    assert "确认任务并生成大纲" in text
    assert "outline_ready_for_approval" in text
    assert "尚无 OutlinePlan" in (
        Path(__file__).resolve().parents[2]
        / "archium"
        / "application"
        / "outline_approval_service.py"
    ).read_text(encoding="utf-8")
