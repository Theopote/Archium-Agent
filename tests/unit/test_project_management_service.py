"""Tests for ProjectManagementService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.project_management_service import ProjectManagementService
from archium.domain.project import Project
from archium.exceptions import ProjectNotFoundError, ValidationError, WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy.orm import Session


def test_create_project(db_session: Session) -> None:
    service = ProjectManagementService(db_session)
    created = service.create_project("新项目", "说明")
    assert created.name == "新项目"
    assert created.description == "说明"
    assert ProjectRepository(db_session).get_by_id(created.id) is not None


def test_create_project_rejects_empty_name(db_session: Session) -> None:
    service = ProjectManagementService(db_session)
    with pytest.raises(ValidationError, match="不能为空"):
        service.create_project("   ")


def test_update_project(db_session: Session) -> None:
    repo = ProjectRepository(db_session)
    project = repo.create(Project(name="原名"))
    db_session.commit()
    fresh = repo.get_by_id(project.id)
    assert fresh is not None

    service = ProjectManagementService(db_session)
    updated = service.update_project(
        fresh.id,
        name="新名",
        description="新描述",
        expected_updated_at=fresh.updated_at,
    )
    assert updated.name == "新名"
    assert updated.description == "新描述"


def test_update_project_rejects_stale_updated_at(db_session: Session) -> None:
    repo = ProjectRepository(db_session)
    project = repo.create(Project(name="原名"))
    db_session.commit()
    stale_updated_at = project.updated_at

    current = repo.get_by_id(project.id)
    assert current is not None
    current.name = "他人已改"
    repo.update(current)
    db_session.commit()

    service = ProjectManagementService(db_session)
    with pytest.raises(WorkflowError, match="刷新"):
        service.update_project(
            project.id,
            name="覆盖",
            expected_updated_at=stale_updated_at,
        )


def test_get_missing_project_raises(db_session: Session) -> None:
    service = ProjectManagementService(db_session)
    with pytest.raises(ProjectNotFoundError):
        service.get_project(uuid4())
