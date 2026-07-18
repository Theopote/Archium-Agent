"""Unit tests for visual UI facade helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.citation import Citation
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from archium.ui.visual_service import (
    get_presentation_visual_snapshot,
    replan_slide,
    run_visual_workflow,
)
from sqlalchemy.orm import Session


@pytest.fixture
def presentation_with_slides(db_session: Session) -> tuple[Project, Presentation]:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="视觉 UI 测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="测试汇报",
            audience="甲方",
            purpose="测试",
            core_message="核心信息一句。",
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
    presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总体规划与空间结构",
            message="总平面确立轴线。",
            slide_type=SlideType.CONTENT,
            key_points=["指标 A", "指标 B"],
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面",
                    preferred_asset_ids=[uuid4()],
                )
            ],
            source_citations=[
                Citation(document_id=uuid4(), document_name="任务书.pdf", page_number=1)
            ],
        )
    )
    db_session.commit()
    return project, presentation


def test_run_visual_workflow_and_snapshot(
    db_session: Session,
    test_settings: object,
    presentation_with_slides: tuple[Project, Presentation],
) -> None:
    project, presentation = presentation_with_slides
    result = run_visual_workflow(
        db_session,
        project.id,
        presentation.id,
        require_art_direction_review=False,
        use_llm=False,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert result.succeeded
    snapshot = get_presentation_visual_snapshot(db_session, presentation.id)
    assert snapshot.art_direction is not None
    assert snapshot.slides
    assert snapshot.slides[0].layout_plan is not None
    assert snapshot.slides[0].visual_intent is not None


def test_replan_slide_drawing_preset(
    db_session: Session,
    test_settings: object,
    presentation_with_slides: tuple[Project, Presentation],
) -> None:
    project, presentation = presentation_with_slides
    run_visual_workflow(
        db_session,
        project.id,
        presentation.id,
        require_art_direction_review=False,
        use_llm=False,
        settings=test_settings,  # type: ignore[arg-type]
    )
    snapshot = get_presentation_visual_snapshot(db_session, presentation.id)
    slide_id = snapshot.slides[0].slide.id
    updated = replan_slide(
        db_session,
        slide_id=slide_id,
        preset="drawing_focus",
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert updated.visual_intent is not None
    assert updated.visual_intent.density_level in set(DensityLevel)
    assert updated.layout_plan is not None
    assert updated.layout_plan.layout_family == LayoutFamily.DRAWING_FOCUS
