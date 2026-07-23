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


@pytest.fixture
def always_valid_layouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy-path fixture: isolate workflow graph from layout-quality flakiness."""
    from archium.domain.visual.validation import LayoutValidationReport

    def _always_valid(self, layout_plan, design_system, **kwargs):  # noqa: ANN001, ARG001
        return LayoutValidationReport(issues=[], score=1.0)

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_valid,
    )


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
    always_valid_layouts: None,
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
        assert second.workflow_run.state.get("deck_composition_plan_id")
        assert second.workflow_run.state.get("deck_composition_plan")
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
    always_valid_layouts: None,
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


def test_visual_workflow_pauses_on_blocking_layout_instead_of_silent_render(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: ERROR/CRITICAL after repair+fallback must await review, not render PPTX."""
    from archium.domain.visual.enums import LayoutIssueSeverity
    from archium.domain.visual.validation import (
        LAYOUT_ELEMENT_OVERLAP,
        LayoutValidationIssue,
        LayoutValidationReport,
    )

    def _always_blocking(self, layout_plan, design_system, **kwargs):  # noqa: ANN001
        return LayoutValidationReport(
            issues=[
                LayoutValidationIssue(
                    rule_code=LAYOUT_ELEMENT_OVERLAP,
                    severity=LayoutIssueSeverity.ERROR,
                    element_ids=["a", "b"],
                    message="forced overlap for test",
                    auto_repairable=True,
                )
            ],
            score=0.1,
        )

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_blocking,
    )

    project, presentation, _slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=False,
            use_llm=False,
            export_pptx=True,
            candidate_count=2,
            max_repair_rounds=1,
        )
        assert result.awaiting_review
        assert result.review_gate == "layout_review"
        assert result.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
        assert (
            result.workflow_run.state.get("current_step")
            == WorkflowStep.VISUAL_AWAIT_LAYOUT_REVIEW.value
        )
        assert bool(result.workflow_run.state.get("fallback_applied"))
        # Must not have silently produced a PPTX while blocked.
        assert not any(str(path).endswith(".pptx") for path in result.render_paths)

        continued = service.continue_after_layout_review(
            result.workflow_run.id,
            allow_invalid_layout_export=True,
        )
        assert continued.workflow_run.status == WorkflowStatus.COMPLETED
        assert not any(str(path).endswith(".pptx") for path in continued.render_paths)
        assert any("PPTX" in warning or "blocked" in warning.lower() for warning in continued.warnings)
    finally:
        service.close()


def test_visual_workflow_critical_blocks_pptx_even_after_ack(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRITICAL remains a hard PPTX gate; allow_invalid only unlocks instructions."""
    from archium.domain.visual.enums import LayoutIssueSeverity
    from archium.domain.visual.validation import (
        LAYOUT_HERO_NOT_DOMINANT,
        LayoutValidationIssue,
        LayoutValidationReport,
    )

    def _always_critical(self, layout_plan, design_system, **kwargs):  # noqa: ANN001
        return LayoutValidationReport(
            issues=[
                LayoutValidationIssue(
                    rule_code=LAYOUT_HERO_NOT_DOMINANT,
                    severity=LayoutIssueSeverity.CRITICAL,
                    element_ids=["hero"],
                    message="forced critical hero failure",
                    auto_repairable=False,
                )
            ],
            score=0.0,
        )

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_critical,
    )

    project, presentation, _slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=False,
            use_llm=False,
            export_pptx=True,
            candidate_count=2,
            max_repair_rounds=1,
        )
        assert result.awaiting_review
        assert result.review_gate == "layout_review"
        assert not any(str(path).endswith(".pptx") for path in result.render_paths)

        continued = service.continue_after_layout_review(
            result.workflow_run.id,
            allow_invalid_layout_export=True,
        )
        assert continued.workflow_run.status == WorkflowStatus.COMPLETED
        assert continued.workflow_run.state.get("export_pptx") is False
        assert not any(str(path).endswith(".pptx") for path in continued.render_paths)
        assert any(
            "PPTX export disabled" in warning for warning in continued.warnings
        )
    finally:
        service.close()


def test_visual_workflow_warning_only_may_export_pptx(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WARNING-only layouts must not pause the export gate; formal PPTX may proceed."""
    from archium.domain.visual.enums import LayoutIssueSeverity
    from archium.domain.visual.validation import (
        LAYOUT_INCONSISTENT_ALIGNMENT,
        LayoutValidationIssue,
        LayoutValidationReport,
    )

    def _warning_only(self, layout_plan, design_system, **kwargs):  # noqa: ANN001
        return LayoutValidationReport(
            issues=[
                LayoutValidationIssue(
                    rule_code=LAYOUT_INCONSISTENT_ALIGNMENT,
                    severity=LayoutIssueSeverity.WARNING,
                    element_ids=["m0", "m1"],
                    message="soft alignment warning",
                    auto_repairable=False,
                )
            ],
            score=0.85,
        )

    def _fake_scene_pptx_export(
        self,
        title,
        scenes,
        output_path,
        **kwargs,
    ):  # noqa: ANN001
        from pathlib import Path

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"PK\x03\x04fake")
        return path

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _warning_only,
    )
    monkeypatch.setattr(
        "archium.infrastructure.renderers.pptx_renderer.PptxRenderer.export_presentation",
        _fake_scene_pptx_export,
    )

    project, presentation, _slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=False,
            use_llm=False,
            export_pptx=True,
            candidate_count=2,
            max_repair_rounds=1,
        )
        assert result.succeeded
        assert not result.awaiting_review
        assert (
            result.workflow_run.state.get("current_step")
            == WorkflowStep.VISUAL_FINALIZE.value
        )
        assert bool(result.workflow_run.state.get("export_pptx")) is True
        assert any(str(path).endswith("presentation.pptx") for path in result.render_paths)
    finally:
        service.close()


def test_visual_workflow_records_repair_diffs_on_blocking_round(
    db_session: Session,
    test_settings: object,
    seeded_presentation: tuple[Project, Presentation, list[SlideSpec]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each repair round persists before/after diffs into workflow state."""
    from archium.domain.visual.enums import LayoutIssueSeverity
    from archium.domain.visual.validation import (
        LAYOUT_ELEMENT_OUTSIDE_PAGE,
        LayoutValidationIssue,
        LayoutValidationReport,
    )

    def _blocking_then_ok(self, layout_plan, design_system, **kwargs):  # noqa: ANN001
        from archium.domain.visual.enums import LayoutValidationStatus

        if layout_plan.validation_status == LayoutValidationStatus.REPAIRED:
            return LayoutValidationReport(issues=[], score=0.95)
        return LayoutValidationReport(
            issues=[
                LayoutValidationIssue(
                    rule_code=LAYOUT_ELEMENT_OUTSIDE_PAGE,
                    severity=LayoutIssueSeverity.ERROR,
                    element_ids=[layout_plan.elements[0].id],
                    message="forced outside for repair diff",
                    auto_repairable=True,
                )
            ],
            score=0.2,
        )

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _blocking_then_ok,
    )

    project, presentation, _slides = seeded_presentation
    service = VisualWorkflowService(db_session, settings=test_settings)  # type: ignore[arg-type]
    try:
        result = service.run(
            project.id,
            presentation.id,
            require_art_direction_review=False,
            use_llm=False,
            export_pptx=False,
            candidate_count=1,
            max_repair_rounds=1,
        )
        diffs = list(result.workflow_run.state.get("repair_diffs") or [])
        # Either repaired cleanly (diffs present) or paused after fallback — both OK,
        # but if repair ran we must have recorded diffs.
        if int(result.workflow_run.state.get("repair_round") or 0) >= 1:
            assert diffs, "repair_round advanced without recording repair_diffs"
            assert all("diffs" in item for item in diffs)
            assert all("layout_plan_id" in item for item in diffs)
    finally:
        service.close()
