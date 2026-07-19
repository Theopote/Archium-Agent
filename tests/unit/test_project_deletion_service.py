"""Tests for ProjectDeletionService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.project_deletion_service import ProjectDeletionService
from archium.config.settings import Settings
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def deletion_settings(tmp_path, monkeypatch) -> Settings:
    base = tmp_path / "deletion-test"
    settings = Settings(
        _env_file=None,
        database_path=base / "archium.db",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
    )
    monkeypatch.setattr("archium.application.project_deletion_service.get_settings", lambda: settings)
    return settings


def test_delete_project_removes_record(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    repo = ProjectRepository(db_session)
    project = repo.create(Project(name="待删除"))
    db_session.commit()

    service = ProjectDeletionService(db_session, settings=deletion_settings)
    result = service.delete_project(project.id)

    assert result.deleted_presentations == 0
    assert repo.get_by_id(project.id) is None


def test_delete_missing_project_raises(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    service = ProjectDeletionService(db_session, settings=deletion_settings)
    with pytest.raises(WorkflowError, match="不存在"):
        service.delete_project(uuid4())
