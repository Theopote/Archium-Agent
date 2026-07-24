"""Unit tests for Streamlit workspace service helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from archium.application.ingestion_service import ImportItemResult
from archium.domain.enums import PresentationType, ProjectType
from archium.ui.workspace_service import (
    build_presentation_request,
    create_project,
    get_project_overview,
    import_uploaded_file,
    list_projects,
)
from sqlalchemy.orm import Session


def test_create_project_and_overview(db_session: Session) -> None:
    project = create_project(
        db_session,
        name="测试项目",
        project_type=ProjectType.HEALTHCARE,
        description="说明",
    )
    db_session.commit()

    overview = get_project_overview(db_session, project.id)
    assert overview is not None
    assert overview.project.name == "测试项目"
    assert overview.document_count == 0
    assert overview.presentation_count == 0

    projects = list_projects(db_session)
    assert any(item.id == project.id for item in projects)


def test_build_presentation_request_parses_sections() -> None:
    request = build_presentation_request(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心结论",
        target_slide_count=8,
        required_sections_text="现状分析\n改造策略",
        presentation_type=PresentationType.CLIENT_REVIEW,
    )
    assert request.title == "概念汇报"
    assert request.required_sections == ["现状分析", "改造策略"]
    assert request.presentation_type == PresentationType.CLIENT_REVIEW


def test_build_presentation_request_supports_chinese_separator() -> None:
    request = build_presentation_request(
        title="汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心结论",
        target_slide_count=6,
        required_sections_text="现状分析、改造策略",
    )
    assert request.required_sections == ["现状分析", "改造策略"]


def test_import_uploaded_file_triggers_reassess(db_session: Session) -> None:
    from pathlib import Path

    project = create_project(db_session, name="上传后刷新", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake_result = ImportItemResult(source_path=Path("brief.pdf"))
    with (
        patch(
            "archium.ui.workspace_service.IngestionService.import_file",
            return_value=fake_result,
        ),
        patch(
            "archium.application.context_intelligence_service.ContextIntelligenceService.reassess"
        ) as reassess,
        patch(
            "archium.infrastructure.llm.factory.create_llm_provider",
            return_value=MagicMock(),
        ),
    ):
        result = import_uploaded_file(
            db_session,
            project.id,
            filename="brief.pdf",
            data=b"%PDF-1.4 fake",
        )
    assert result is fake_result
    reassess.assert_called_once_with(project.id)


def test_import_uploaded_file_survives_reassess_failure(db_session: Session) -> None:
    from pathlib import Path

    project = create_project(db_session, name="上传容错", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake_result = ImportItemResult(source_path=Path("site.jpg"))
    with (
        patch(
            "archium.ui.workspace_service.IngestionService.import_file",
            return_value=fake_result,
        ),
        patch(
            "archium.application.context_intelligence_service.ContextIntelligenceService.reassess",
            side_effect=RuntimeError("llm down"),
        ),
        patch(
            "archium.infrastructure.llm.factory.create_llm_provider",
            return_value=MagicMock(),
        ),
    ):
        result = import_uploaded_file(
            db_session,
            project.id,
            filename="site.jpg",
            data=b"fake-image",
        )
    assert result.error is None
