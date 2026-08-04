"""Deck QA / critic artifacts must reload from workflow runs after session loss."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import WorkflowStatus
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.ui.visual_service import (
    get_presentation_visual_snapshot,
    load_persisted_visual_qa_artifacts,
)
from sqlalchemy.orm import Session


def test_load_persisted_visual_qa_from_workflow_run(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="QA 持久化"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="滨江测试汇报")
    )
    deck_qa = {
        "total_score": 0.91,
        "blocker_count": 0,
        "warning_count": 1,
        "findings": [],
    }
    WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=project.id,
            presentation_id=presentation.id,
            status=WorkflowStatus.COMPLETED,
            state={
                "workflow_kind": "visual_composition",
                "deck_qa_report": deck_qa,
                "visual_critic_reports": [{"slide_id": str(uuid4()), "score": 0.8}],
                "render_paths": ["C:/tmp/slide_001.png"],
                "output_dir": "C:/tmp/visual-out",
            },
        )
    )
    db_session.commit()

    critics, loaded_deck, paths, output_dir = load_persisted_visual_qa_artifacts(
        db_session, presentation.id
    )
    assert loaded_deck == deck_qa
    assert critics is not None and len(critics) == 1
    assert paths == ["C:/tmp/slide_001.png"]
    assert output_dir == "C:/tmp/visual-out"

    snapshot = get_presentation_visual_snapshot(db_session, presentation.id)
    assert snapshot.deck_qa_report == deck_qa
    assert len(snapshot.visual_critic_reports) == 1


def test_injected_deck_qa_wins_over_persisted(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="QA 覆盖"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="覆盖测试")
    )
    WorkflowRunRepository(db_session).create(
        WorkflowRun(
            project_id=project.id,
            presentation_id=presentation.id,
            status=WorkflowStatus.COMPLETED,
            state={
                "workflow_kind": "visual_composition",
                "deck_qa_report": {"total_score": 0.5, "blocker_count": 1},
            },
        )
    )
    db_session.commit()

    live = {"total_score": 0.99, "blocker_count": 0}
    snapshot = get_presentation_visual_snapshot(
        db_session,
        presentation.id,
        deck_qa_report=live,
        visual_critic_reports=[],
        preview_paths=[],
    )
    assert snapshot.deck_qa_report == live
