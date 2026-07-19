"""Integration tests for visual edit service."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.citation import Citation
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def slide_with_visual(db_session: Session) -> SlideSpec:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="编辑测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="编辑汇报")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="编辑汇报",
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
    asset_id = uuid4()
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="测试页",
            message="测试核心信息。",
            slide_type=SlideType.CONTENT,
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面",
                    preferred_asset_ids=[asset_id],
                )
            ],
            source_citations=[
                Citation(document_id=uuid4(), document_name="任务书.pdf", page_number=1)
            ],
        )
    )
    db_session.commit()
    return slide


def test_apply_reduce_text_records_revision_and_replans(
    db_session: Session,
    slide_with_visual: SlideSpec,
) -> None:
    service = VisualEditService(db_session)
    first = service.apply_intent(slide_with_visual.id, VisualEditIntent.REDUCE_TEXT)
    assert first.layout_plan is not None
    assert first.visual_intent is not None
    assert "减少文字" in first.visual_intent.composition_strategy or first.visual_intent.density_level.value == "spacious"

    second = service.apply_intent(slide_with_visual.id, VisualEditIntent.INCREASE_WHITESPACE)
    assert second.layout_plan is not None

    restored = service.restore_previous(slide_with_visual.id)
    assert restored.restored is True
    assert restored.layout_plan is not None
