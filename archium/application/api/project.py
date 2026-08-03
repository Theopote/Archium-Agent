"""/project — project identity CRUD facade."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_management_service import ProjectManagementService
from archium.domain.enums import ProjectOriginMode, ProjectStatus
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.infrastructure.database.repositories import PresentationRepository


class ProjectApi:
    def __init__(self, session: Session) -> None:
        self._service = ProjectManagementService(session)
        self._presentations = PresentationRepository(session)

    def list(
        self,
        *,
        status: ProjectStatus | None = None,
        actor_id: str | None = None,
    ) -> list[Project]:
        return self._service.list_projects(status=status, actor_id=actor_id)

    def get(self, project_id: UUID) -> Project:
        return self._service.get_project(project_id)

    def create(
        self,
        name: str,
        description: str | None = None,
        *,
        origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT,
        actor_id: str | None = None,
        organization_id: UUID | None = None,
    ) -> Project:
        return self._service.create_project(
            name,
            description,
            origin_mode=origin_mode,
            actor_id=actor_id,
            organization_id=organization_id,
        )

    def update(
        self,
        project_id: UUID,
        *,
        name: str,
        description: str | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Project:
        return self._service.update_project(
            project_id,
            name=name,
            description=description,
            expected_updated_at=expected_updated_at,
        )

    def list_presentations(self, project_id: UUID) -> list[Presentation]:
        return self._presentations.list_by_project(project_id)
