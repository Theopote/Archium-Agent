"""Integration test for XLSX metric extraction at ingest."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.ingestion_service import IngestionService
from archium.domain.enums import ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from sqlalchemy.orm import Session

from tests.fixtures.sample_files import create_sample_xlsx


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(
        Project(name="指标表项目", project_type=ProjectType.HEALTHCARE)
    )


def test_import_xlsx_extracts_site_area_fact(
    db_session: Session,
    project: Project,
    tmp_path: Path,
    test_settings: object,
) -> None:
    xlsx_path = create_sample_xlsx(tmp_path / "指标.xlsx")
    result = IngestionService(db_session, settings=test_settings).import_file(  # type: ignore[arg-type]
        project.id,
        xlsx_path,
    )

    assert result.error is None
    facts = FactRepository(db_session).list_by_project(project.id)
    assert any(fact.key == "site_area" for fact in facts)
