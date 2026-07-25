"""Unit tests for ProjectProcessBoard derivation."""

from __future__ import annotations

from archium.application.process import build_project_process_board
from archium.domain.concept_direction import ConceptDirection
from archium.domain.document import SourceDocument
from archium.domain.enums import (
    ConceptDirectionStatus,
    DocumentType,
    ExplorationSessionStatus,
    PresentationStatus,
    ProcessingStatus,
    VerificationStatus,
)
from archium.domain.exploration_session import ExplorationSession
from archium.domain.fact import ProjectFact
from archium.domain.presentation import Presentation
from archium.domain.process import DesignProcessFocus, ProjectProcessPhase
from archium.domain.project import Project
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    DocumentRepository,
    ExplorationSessionRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
    VisualConceptBriefRepository,
)


def test_process_board_idle_for_empty_project(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="空项目"))
    db_session.commit()
    board = build_project_process_board(db_session, project.id)
    assert board.research.phase == ProjectProcessPhase.IDLE
    assert board.design.phase == ProjectProcessPhase.IDLE
    assert board.presentation.phase == ProjectProcessPhase.IDLE
    assert "研究" in board.summary_line()


def test_process_board_research_active_on_pending_fact(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="医院"))
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="location",
            label="地点",
            value="西安",
            verification_status=VerificationStatus.EXTRACTED,
        )
    )
    db_session.commit()
    board = build_project_process_board(db_session, project.id)
    assert board.research.phase == ProjectProcessPhase.ACTIVE


def test_process_board_design_and_presentation(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="改造"))
    DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="brief.pdf",
            original_path="brief.pdf",
            stored_path="brief.pdf",
            file_type=DocumentType.OTHER,
            file_hash="b" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    ExplorationSessionRepository(db_session).create(
        ExplorationSession(
            project_id=project.id,
            idea_text="旧楼改造概念",
            status=ExplorationSessionStatus.DIRECTION_SELECTED,
        )
    )
    PresentationRepository(db_session).create_presentation(
        Presentation(
            project_id=project.id,
            title="概念汇报",
            status=PresentationStatus.IN_PROGRESS,
        )
    )
    db_session.commit()
    board = build_project_process_board(db_session, project.id)
    assert board.research.phase == ProjectProcessPhase.READY
    assert board.design.phase == ProjectProcessPhase.READY
    assert board.design.focus == DesignProcessFocus.DIRECTION_SELECTED.value
    assert board.presentation.phase == ProjectProcessPhase.ACTIVE
    assert board.presentation.active_id is not None
    assert "方向已选" in board.summary_line()


def test_design_pointer_comparing_directions(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="方向比较"))
    exploration = ExplorationSessionRepository(db_session).create(
        ExplorationSession(
            project_id=project.id,
            idea_text="多方向探索",
            status=ExplorationSessionStatus.EXPLORING,
        )
    )
    ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            exploration_session_id=exploration.id,
            title="庭院优先",
            status=ConceptDirectionStatus.DRAFT,
            sort_order=0,
        )
    )
    ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            exploration_session_id=exploration.id,
            title="街巷织补",
            status=ConceptDirectionStatus.DRAFT,
            sort_order=1,
        )
    )
    db_session.commit()
    board = build_project_process_board(db_session, project.id)
    assert board.design.phase == ProjectProcessPhase.ACTIVE
    assert board.design.focus == DesignProcessFocus.COMPARING_DIRECTIONS.value
    assert board.design.active_id == exploration.id
    assert board.design.secondary_id is not None
    assert "2 个概念方向" in board.design.label


def test_design_pointer_visual_ready_and_failed(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="视觉闭环"))
    exploration = ExplorationSessionRepository(db_session).create(
        ExplorationSession(
            project_id=project.id,
            idea_text="示意出图",
            status=ExplorationSessionStatus.DIRECTION_SELECTED,
        )
    )
    selected = ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            exploration_session_id=exploration.id,
            title="林缘退台",
            status=ConceptDirectionStatus.SELECTED,
        )
    )
    exploration.selected_direction_id = selected.id
    ExplorationSessionRepository(db_session).update(exploration)
    VisualConceptBriefRepository(db_session).create(
        VisualConceptBrief(
            project_id=project.id,
            concept_direction_id=selected.id,
            title="林缘示意",
            status="imaged",
        )
    )
    db_session.commit()
    board = build_project_process_board(db_session, project.id)
    assert board.design.phase == ProjectProcessPhase.READY
    assert board.design.focus == DesignProcessFocus.VISUAL_READY.value
    assert board.design.active_id == selected.id
    assert board.design.secondary_id is not None
    assert "视觉就绪" in board.design.label

    # Latest brief failed → blocked
    VisualConceptBriefRepository(db_session).create(
        VisualConceptBrief(
            project_id=project.id,
            concept_direction_id=selected.id,
            title="重试失败",
            status="failed",
            error_message="provider unavailable",
        )
    )
    db_session.commit()
    board2 = build_project_process_board(db_session, project.id)
    assert board2.design.phase == ProjectProcessPhase.BLOCKED
    assert board2.design.focus == DesignProcessFocus.VISUAL_FAILED.value
    assert "provider unavailable" in board2.design.detail
