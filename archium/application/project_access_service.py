"""Project access control — membership + permission gates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.access import (
    LOCAL_ACTOR_ID,
    ProjectMember,
    ProjectPermission,
    ProjectRole,
)
from archium.exceptions import AccessDeniedError
from archium.infrastructure.database.repositories import ProjectMemberRepository


class ProjectAccessService:
    """Minimal RBAC for Owner / Architect / Reviewer / Client."""

    def __init__(self, session: Session) -> None:
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

    def can(
        self,
        project_id: UUID,
        actor_id: str,
        permission: ProjectPermission,
    ) -> bool:
        member = self._repo.get_by_project_actor(project_id, actor_id)
        if member is None:
            # Bootstrap: projects without members allow local-user edit (single-user mode).
            if actor_id == LOCAL_ACTOR_ID and permission in {
                ProjectPermission.VIEW,
                ProjectPermission.EDIT,
                ProjectPermission.REVIEW,
                ProjectPermission.EXPORT,
                ProjectPermission.MANAGE_MEMBERS,
            }:
                return True
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
