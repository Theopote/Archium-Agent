"""Unit tests for DeliveryRecordService."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from archium.application.delivery_record_service import DeliveryRecordService
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DeliveryRecordRepository,
    PresentationRepository,
    ProjectRepository,
)


def test_record_export_persists(db_session: Session, tmp_path: Path) -> None:
    project = ProjectRepository(db_session).create(Project(name="交付记录"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="导出测试")
    )
    artifact = tmp_path / "deck.pptx"
    artifact.write_bytes(b"pptx-bytes")

    saved = DeliveryRecordService(db_session).record_export(
        project_id=project.id,
        presentation_id=presentation.id,
        format="PPTX",
        file_uri=str(artifact),
        qa_status="passed",
    )
    db_session.commit()

    assert saved.file_hash
    assert saved.format == "PPTX"
    rows = DeliveryRecordRepository(db_session).list_by_project(project.id)
    assert len(rows) == 1
    assert rows[0].file_uri == str(artifact)
    assert rows[0].qa_status == "passed"
