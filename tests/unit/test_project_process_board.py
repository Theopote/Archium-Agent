"""Unit tests for ProjectProcessBoard derivation."""

from __future__ import annotations

from archium.application.process import build_project_process_board
from archium.domain.enums import (
    DocumentType,
    ExplorationSessionStatus,
    PresentationStatus,
    ProcessingStatus,
    VerificationStatus,
)
from archium.domain.exploration_session import ExplorationSession
from archium.domain.fact import ProjectFact
from archium.domain.presentation import Presentation
from archium.domain.process import ProjectProcessPhase
from archium.domain.project import Project
from archium.domain.document import SourceDocument
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    ExplorationSessionRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
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
    assert board.presentation.phase == ProjectProcessPhase.ACTIVE
    assert board.presentation.active_id is not None
