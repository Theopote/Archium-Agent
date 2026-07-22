"""Deliver readiness metrics and persisted export records."""

from __future__ import annotations

from pathlib import Path

from archium.application.delivery_record_service import DeliveryRecordService
from archium.config.settings import Settings
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import (
    DeliveryRecordRepository,
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.database.session import create_engine_from_settings

ROOT = Path(__file__).resolve().parents[2]
DELIVER = ROOT / "archium" / "ui" / "pages" / "flow" / "deliver.py"


def test_deliver_readiness_shows_pending_warnings_and_blockers() -> None:
    text = DELIVER.read_text(encoding="utf-8")
    assert "页面完成" in text
    assert "待完成页" in text
    assert 'metric("PPTX"' in text or 'metric("PPTX",' in text
    assert 'metric("PDF"' in text or 'metric("PDF",' in text
    assert "阻塞项" in text
    assert "项目资料" in text
    assert "evidence_readiness_service" in text
    assert "_render_delivery_record_actions" in text
    # Must not collapse warnings into the pending metric.
    assert "pending if pending else warn_count" not in text


def test_export_panel_warns_when_record_persist_fails() -> None:
    export = (
        ROOT / "archium" / "ui" / "studio" / "export_panel.py"
    ).read_text(encoding="utf-8")
    assert "DeliveryRecordResult" in export
    assert "版本记录保存失败" in export
    assert "except Exception:\n        pass" not in export


def test_delivery_records_survive_new_session(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Simulate app restart: write with one session, read with another engine."""
    import archium.infrastructure.database.models  # noqa: F401

    engine = create_engine_from_settings(test_settings)
    Base.metadata.create_all(engine)

    artifact = tmp_path / "export.pptx"
    artifact.write_bytes(b"pptx-bytes")

    from sqlalchemy.orm import Session as SASession

    with SASession(bind=engine, autoflush=False, autocommit=False) as session:
        project = ProjectRepository(session).create(Project(name="持久导出"))
        presentation = PresentationRepository(session).create_presentation(
            Presentation(project_id=project.id, title="版本 A")
        )
        saved = DeliveryRecordService(session).record_export(
            project_id=project.id,
            presentation_id=presentation.id,
            format="PPTX",
            file_uri=str(artifact),
            qa_status="passed",
        )
        session.commit()
        project_id = project.id
        record_id = saved.id

    engine.dispose()

    engine2 = create_engine_from_settings(test_settings)
    with SASession(bind=engine2, autoflush=False, autocommit=False) as session2:
        rows = DeliveryRecordRepository(session2).list_by_project(project_id)
        assert len(rows) == 1
        assert rows[0].id == record_id
        assert rows[0].format == "PPTX"
        assert rows[0].file_uri == str(artifact)
        assert rows[0].file_hash
    engine2.dispose()


def test_deliver_page_reads_delivery_record_service() -> None:
    text = DELIVER.read_text(encoding="utf-8")
    assert "DeliveryRecordService" in text
    assert "list_for_presentation" in text
