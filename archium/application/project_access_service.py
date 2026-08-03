"""Project access control — membership + permission gates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.access import (
    LOCAL_ACTOR_ID,
    ProjectMember,
    ProjectPermission,
    ProjectRole,
)
from archium.domain.project import Project
from archium.exceptions import AccessDeniedError
from archium.infrastructure.database.repositories import (
    ProjectMemberRepository,
    ProjectRepository,
)


class ProjectAccessService:
    """Minimal RBAC for Owner / Architect / Reviewer / Client."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._repo = ProjectMemberRepository(session)

    def ensure_default_owner(
        self,
        project_id: UUID,
        *,
        actor_id: str = LOCAL_ACTOR_ID,
        display_name: str = "本地用户",
    ) -> ProjectMember:
        existing = self._repo.get_by_project_actor(project_id, actor_id)
        if existing is not None:
            return existing
        return self._repo.create(
            ProjectMember(
                project_id=project_id,
                actor_id=actor_id,
                display_name=display_name,
                role=ProjectRole.OWNER,
            )
        )

    def add_member(
        self,
        project_id: UUID,
        actor_id: str,
        role: ProjectRole,
        *,
        display_name: str = "",
        actor: str | None = None,
    ) -> ProjectMember:
        if actor is not None:
            self.require(project_id, actor, ProjectPermission.MANAGE_MEMBERS)
        existing = self._repo.get_by_project_actor(project_id, actor_id)
        if existing is not None:
            existing.role = role
            if display_name:
                existing.display_name = display_name
            existing.touch()
            return self._repo.update(existing)
        return self._repo.create(
            ProjectMember(
                project_id=project_id,
                actor_id=actor_id,
                display_name=display_name or actor_id,
                role=role,
            )
        )

    def list_members(self, project_id: UUID) -> list[ProjectMember]:
        return self._repo.list_for_project(project_id)

    def get_member(self, project_id: UUID, actor_id: str) -> ProjectMember | None:
        return self._repo.get_by_project_actor(project_id, actor_id)

    def list_visible_projects(self, actor_id: str) -> list[Project]:
        """Projects the actor can see.

        - Has memberships → those projects only.
        - ``local-user`` with zero memberships → compat ``list_all`` (single-seat).
        - Other actors with zero memberships → empty.
        """
        projects = ProjectRepository(self._session)
        resolved = (actor_id or "").strip() or LOCAL_ACTOR_ID
        ids = self._repo.list_project_ids_for_actor(resolved)
        if ids:
            rows: list[Project] = []
            for project_id in ids:
                item = projects.get_by_id(project_id)
                if item is not None:
                    rows.append(item)
            return rows
        if resolved == LOCAL_ACTOR_ID:
            return projects.list_all()
        return []

    def can(
        self,
        project_id: UUID,
        actor_id: str,
        permission: ProjectPermission,
    ) -> bool:
        member = self._repo.get_by_project_actor(project_id, actor_id)
        if member is None:
            # Topic 08 C1 / SEC-001: legacy empty projects → promote local-user to owner
            if actor_id == LOCAL_ACTOR_ID:
                member = self.ensure_default_owner(project_id)
                return member.can(permission)
            return False
        return member.can(permission)

    def require(
        self,
        project_id: UUID,
        actor_id: str,
        permission: ProjectPermission,
    ) -> ProjectMember | None:
        if not self.can(project_id, actor_id, permission):
            raise AccessDeniedError(
                f"Actor '{actor_id}' lacks '{permission.value}' on project {project_id}",
                project_id=project_id,
                actor_id=actor_id,
                permission=permission.value,
            )
        return self._repo.get_by_project_actor(project_id, actor_id)
