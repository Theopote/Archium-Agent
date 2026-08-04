"""/project — project identity CRUD facade."""

from __future__ import annotations

import builtins
from datetime import datetime
from uuid import UUID

from archium.application.project_management_service import ProjectManagementService
from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.asset import Asset
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import ProjectOriginMode, ProjectStatus, ProjectType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.database.repositories import PresentationRepository


class ProjectApi:
    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._service = ProjectManagementService(session)
        self._presentations = PresentationRepository(session)

    def list(
        self,
        *,
        status: ProjectStatus | None = None,
        actor_id: str | None = None,
    ) -> builtins.list[Project]:
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
        project_type: ProjectType | None = None,
    ) -> Project:
        project = self._service.create_project(
            name,
            description,
            origin_mode=origin_mode,
            actor_id=actor_id,
            organization_id=organization_id,
        )
        if project_type is not None and project.project_type != project_type:
            project.project_type = project_type
            from archium.infrastructure.database.repositories import ProjectRepository

            project = ProjectRepository(self._session).update(project)
            self._session.flush()
        return project

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

    def list_presentations(self, project_id: UUID) -> builtins.list[Presentation]:
        return self._presentations.list_by_project(project_id)

    def count_presentations(self, project_id: UUID) -> int:
        return self._presentations.count_by_project(project_id)

    def get_asset(self, asset_id: UUID) -> Asset | None:
        from archium.infrastructure.database.repositories import AssetRepository

        return AssetRepository(self._session).get_by_id(asset_id)

    def list_assets(self, project_id: UUID) -> builtins.list[Asset]:
        from archium.infrastructure.database.repositories import AssetRepository

        return AssetRepository(self._session).list_by_project(project_id)

    def list_cultural_narratives(self, project_id: UUID) -> builtins.list[CulturalNarrativePlan]:
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).list_cultural_narratives(project_id)

    def list_renovation_issue_maps(self, project_id: UUID) -> builtins.list[RenovationIssueMap]:
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).list_renovation_issue_maps(project_id)

    def list_reference_style_profiles(
        self, project_id: UUID
    ) -> builtins.list[ReferenceStyleProfile]:
        from archium.infrastructure.database.repositories import ProjectRepository

        return ProjectRepository(self._session).list_reference_style_profiles(project_id)
