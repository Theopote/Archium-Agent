"""Integration tests for visual composition workflow."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.visual_workflow_service import VisualWorkflowService
from archium.domain.citation import Citation
from archium.domain.enums import (
    ApprovalStatus,
    SlideType,
    VisualType,
    WorkflowStatus,
    WorkflowStep,
)
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def seeded_presentation(db_session: Session) -> tuple[Project, Presentation, list[SlideSpec]]:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="视觉编排测试项目"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="医院改扩建汇报")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="医院改扩建汇报",
            audience="院方领导",
            purpose="汇报现状问题与改造策略",
            core_message="以患者路径为中心改善就医体验。",
            tone="专业克制",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="入口混乱与候诊压力是核心问题。",
            chapters=[],
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)

    doc_id = uuid4()
    slides = [
        presentations.save_slide(
            SlideSpec(
                presentation_id=presentation.id,
                chapter_id="ch1",
                order=0,
                title="总体规划与空间结构",
                message="总平面确立院落轴线与核心公服节点。",
                slide_type=SlideType.CONTENT,
                key_points=["绿地率 42%", "容积率 1.8", "轴线贯通"],
                visual_requirements=[
                    VisualRequirement(
                        type=VisualType.SITE_PLAN,
                        description="总平面图",
                        preferred_asset_ids=[uuid4()],
                    )
                ],
                source_citations=[
                    Citation(document_id=doc_id, document_name="总体规划.pdf", page_number=2)
                ],
            )
        ),
        presentations.save_slide(
            SlideSpec(
                presentation_id=presentation.id,
                chapter_id="ch1",
                order=1,
                title="患者就医过程中的高压力节点",
                message="焦虑来自入口混乱、路径不清和长时间候诊。",
                slide_type=SlideType.CONTENT,
                key_points=["入口混乱", "路径不清", "候诊过长", "问询反复"],
                visual_requirements=[
                    VisualRequirement(
                        type=VisualType.SITE_PHOTO,
                        description=f"现场{i}",
                        preferred_asset_ids=[uuid4()],
                    )
                    for i in range(4)
                ],
                source_citations=[
                    Citation(document_id=doc_id, document_name="踏勘记录.pdf", page_number=1)
                ],
            )
        ),
    ]
    db_session.commit()
    return project, presentation, slides


def test_visual_workflow_pauses_for_art_direction_approval(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
) -> None:
    project, presentation, _slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=True,
            use_llm=False,
            export_layout_instructions=True,
            export_pptx=False,
            candidate_count=2,
        )
        assert result.awaiting_review
        assert result.review_gate == "art_direction"
        assert result.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
        assert result.art_direction is not None
        assert result.art_direction.approval_status == ApprovalStatus.PENDING
        assert (
            result.workflow_run.state.get("current_step")
            == WorkflowStep.VISUAL_AWAIT_ART_DIRECTION_APPROVAL.value
        )
    finally:
        service.close()


def test_visual_workflow_completes_after_art_direction_approval(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
) -> None:
    project, presentation, slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        first = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=True,
            use_llm=False,
            candidate_count=2,
        )
        assert first.awaiting_review

        second = service.continue_after_art_direction_approval(first.workflow_run.id)
        assert not second.awaiting_review
        assert second.succeeded
        assert second.workflow_run.status == WorkflowStatus.COMPLETED
        assert len(second.visual_intent_ids) == len(slides)
        assert len(second.layout_plan_ids) == len(slides)
        assert second.render_paths
        assert any(path.endswith(".json") for path in second.render_paths)
        assert second.design_system is not None
        assert second.art_direction is not None
        assert second.art_direction.approval_status == ApprovalStatus.APPROVED
        # No API keys leaked into persisted state.
        state_blob = str(second.workflow_run.state).lower()
        assert "api_key" not in state_blob
        assert "secret" not in state_blob
    finally:
        service.close()


def test_visual_workflow_can_skip_art_direction_gate(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
) -> None:
    project, presentation, slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=False,
            use_llm=False,
            candidate_count=2,
        )
        assert result.succeeded
        assert len(result.layout_plan_ids) == len(slides)
        assert result.workflow_run.state.get("current_step") == WorkflowStep.VISUAL_FINALIZE.value
    finally:
        service.close()
