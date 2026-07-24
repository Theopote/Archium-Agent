"""Application service for listing and mutating projects from the UI."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import ProjectOriginMode, ProjectStatus
from archium.domain.project import Project
from archium.exceptions import ProjectNotFoundError, ValidationError, WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="project_management")


class ProjectManagementService:
    """CRUD operations for project records (UI-facing)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._projects = ProjectRepository(session)

    def list_projects(self, *, status: ProjectStatus | None = None) -> list[Project]:
        return self._projects.list_all(status=status)

    def get_project(self, project_id: UUID) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def create_project(
        self,
        name: str,
        description: str | None = None,
        *,
        origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT,
    ) -> Project:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("项目名称不能为空")

        cleaned_description = description.strip() if description else None
        if cleaned_description == "":
            cleaned_description = None

        project = Project(
            name=cleaned_name,
            description=cleaned_description,
            origin_mode=origin_mode,
        )
        created = self._projects.create(project)
        # APP-003: use-case boundary owns commit (UI must not).
        self._session.commit()
        logger.info("Created project %s", created.id)
        return created

    def update_project(
        self,
        project_id: UUID,
        *,
        name: str,
        description: str | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        if expected_updated_at is not None and project.updated_at != expected_updated_at:
            raise WorkflowError("项目已被其他操作更新，请刷新后重试。")

        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("项目名称不能为空")

        cleaned_description = description.strip() if description else None
        if cleaned_description == "":
            cleaned_description = None

        project.name = cleaned_name
        project.description = cleaned_description
        project.touch()
        updated = self._projects.update(project)
        self._session.commit()
        logger.info("Updated project %s", project_id)
        return updated
