"""Round-trip QA must reload from delivery records after session loss."""

from __future__ import annotations

from uuid import uuid4

from archium.application.delivery_record_service import DeliveryRecordService
from archium.domain.export_round_trip import ExportRoundTripReport, RoundTripStatus
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from archium.ui.delivery.fidelity_report_panel import load_persisted_round_trip_report
from sqlalchemy.orm import Session


def test_load_persisted_round_trip_from_delivery_record(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="RT 持久化"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Round-trip 测试")
    )
    report = ExportRoundTripReport(
        presentation_id=presentation.id,
        status=RoundTripStatus.PASS,
        text_match_rate=1.0,
        geometry_match_rate=0.95,
        similarity_score=0.92,
        slides=[],
    )
    DeliveryRecordService(db_session).record_export(
        project_id=project.id,
        presentation_id=presentation.id,
        format="PPTX",
        file_uri=f"C:/tmp/{uuid4()}.pptx",
        qa_status="pass",
        round_trip_report=report.model_dump(mode="json"),
    )
    db_session.commit()

    loaded = load_persisted_round_trip_report(presentation.id, session=db_session)
    assert loaded is not None
    assert loaded.status == RoundTripStatus.PASS
    assert loaded.similarity_score == 0.92
