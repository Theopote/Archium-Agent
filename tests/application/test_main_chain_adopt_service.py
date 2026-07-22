"""Tests for MainChainAdoptService and radar adopt → main-chain bindings."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from archium.application.delivery_record_service import DeliveryRecordService
from archium.application.main_chain_adopt_catalog import MAIN_CHAIN_ADOPT_BINDINGS
from archium.application.main_chain_adopt_service import MainChainAdoptService
from archium.application.presentation_technology_radar_catalog import DEFAULT_RADAR_SYSTEMS
from archium.domain.enums import ApprovalStatus, EvidenceAvailability, NarrativeStage
from archium.domain.main_chain_adopt import AdoptLandingStatus
from archium.domain.narrative_arc import NarrativeArc, NarrativePosition
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Chapter, Presentation, Storyline
from archium.domain.project import Project
from archium.ui.pages.flow import evaluate_stage_gate
from archium.ui.project_progress_card import ProjectProgressSnapshot
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


def test_adopt_bindings_cover_radar_adopt_concepts() -> None:
    adopt_labels = {
        concept
        for system in DEFAULT_RADAR_SYSTEMS
        if system.archium_relevance == "adopt"
        for concept in system.concepts_to_adopt
    }
    bound_labels = {binding.label_zh for binding in MAIN_CHAIN_ADOPT_BINDINGS}
    assert len(MAIN_CHAIN_ADOPT_BINDINGS) == 15
    assert adopt_labels == bound_labels


def test_platform_builtin_concepts_marked_landed(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="采纳测试"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="汇报")
    )
    db_session.commit()

    report = MainChainAdoptService(db_session).evaluate(
        project.id,
        presentation_id=presentation.id,
    )
    platform = [
        item
        for item in report.checkpoints
        if item.binding.platform_builtin
    ]
    assert len(platform) == 6
    assert all(item.status == AdoptLandingStatus.PLATFORM for item in platform)


def test_missing_narrative_arc_blocks_outline_stage(db_session: Session) -> None:
    project, presentation = _seed_presentation(db_session)
    presentations = PresentationRepository(db_session)
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点",
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
    )
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    db_session.commit()

    report = MainChainAdoptService(db_session).evaluate(
        project.id,
        presentation_id=presentation.id,
    )
    narrative = next(
        item
        for item in report.checkpoints
        if item.binding.concept_id == "slide_deck_narrative_arc"
    )
    assert narrative.status == AdoptLandingStatus.GAP
    assert narrative.blocks_stage_advance
    assert report.stage_blockers("outline")


def test_narrative_arc_landed_when_sections_positioned(db_session: Session) -> None:
    project, presentation = _seed_presentation(db_session)
    presentations = PresentationRepository(db_session)
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点",
            narrative_arc=NarrativeArc(
                opening_context="背景",
                central_problem="问题",
                tension_building=["矛盾"],
                turning_point="转折",
                proposed_resolution="方案",
                final_decision="决策",
            ),
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
    )
    outline = presentations.save_outline(
        OutlinePlan(
            presentation_id=presentation.id,
            title="大纲",
            thesis="论点",
            audience="甲方",
            purpose="决策",
            sections=[
                OutlineSection(
                    id="s1",
                    title="现状",
                    purpose="诊断",
                    key_message="风险",
                    order=0,
                    narrative_position=NarrativePosition(stage=NarrativeStage.PROBLEM),
                )
            ],
        )
    )
    presentation.current_storyline_id = storyline.id
    presentation.current_outline_id = outline.id
    presentations.update_presentation(presentation)
    db_session.commit()

    report = MainChainAdoptService(db_session).evaluate(
        project.id,
        presentation_id=presentation.id,
    )
    narrative = next(
        item
        for item in report.checkpoints
        if item.binding.concept_id == "slide_deck_narrative_arc"
    )
    assert narrative.status == AdoptLandingStatus.LANDED


def test_delivery_render_qa_landed_with_round_trip(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project, presentation = _seed_presentation(db_session)
    artifact = tmp_path / "deck.pptx"
    artifact.write_bytes(b"pptx")
    DeliveryRecordService(db_session).record_export(
        project_id=project.id,
        presentation_id=presentation.id,
        format="PPTX",
        file_uri=str(artifact),
        qa_status="passed",
        round_trip_report={"status": "passed"},
    )
    db_session.commit()

    report = MainChainAdoptService(db_session).evaluate(
        project.id,
        presentation_id=presentation.id,
    )
    render_qa = next(
        item
        for item in report.checkpoints
        if item.binding.concept_id == "slideweaver_render_qa"
    )
    assert render_qa.status == AdoptLandingStatus.LANDED


def test_outline_gate_merges_narrative_arc_blocker(db_session: Session) -> None:
    project, presentation = _seed_presentation(db_session)
    presentations = PresentationRepository(db_session)
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点",
            chapters=[],
            approval_status=ApprovalStatus.PENDING,
        )
    )
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    db_session.commit()

    snapshot = ProjectProgressSnapshot(
        project_id=project.id,
        project_name=project.name,
        presentation_id=presentation.id,
        presentation_title=presentation.title,
        presentation_type=None,
        document_count=1,
        slide_count=0,
        layout_ready_count=0,
        has_brief=True,
        has_outline=True,
        outline_approved=True,
        design_briefs_approved=True,
        design_briefs_total=1,
        design_briefs_approved_count=1,
        ready_for_export=False,
        updated_at=presentation.updated_at,
        evidence_availability=EvidenceAvailability.AVAILABLE,
        export_blocker_count=0,
    )

    @contextmanager
    def _fake_get_session(*_args: object, **_kwargs: object):
        yield db_session

    with patch(
        "archium.infrastructure.database.session.get_session",
        _fake_get_session,
    ):
        gate = evaluate_stage_gate("outline", snapshot)
    assert any("叙事弧线" in item for item in gate.blockers)


def _seed_presentation(db_session: Session) -> tuple[Project, Presentation]:
    project = ProjectRepository(db_session).create(Project(name="主链采纳"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    return project, presentation
