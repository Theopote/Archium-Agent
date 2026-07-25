"""Project access control — minimal multi-role foundation (single-user ready)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel

LOCAL_ACTOR_ID = "local-user"


class ProjectRole(StrEnum):
    OWNER = "owner"
    ARCHITECT = "architect"
    REVIEWER = "reviewer"
    CLIENT = "client"


class ProjectPermission(StrEnum):
    VIEW = "view"
    EDIT = "edit"
    REVIEW = "review"
    MANAGE_MEMBERS = "manage_members"
    EXPORT = "export"


_ROLE_PERMISSIONS: dict[ProjectRole, frozenset[ProjectPermission]] = {
    ProjectRole.OWNER: frozenset(ProjectPermission),
    ProjectRole.ARCHITECT: frozenset(
        {
            ProjectPermission.VIEW,
            ProjectPermission.EDIT,
            ProjectPermission.REVIEW,
            ProjectPermission.EXPORT,
        }
    ),
    ProjectRole.REVIEWER: frozenset(
        {
            ProjectPermission.VIEW,
            ProjectPermission.REVIEW,
            ProjectPermission.EXPORT,
        }
    ),
    ProjectRole.CLIENT: frozenset(
        {
            ProjectPermission.VIEW,
            ProjectPermission.EXPORT,
        }
    ),
}


class ProjectMember(IdentifiedModel, TimestampedModel):
    """One actor's membership on a project."""

    project_id: UUID
    actor_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)
    role: ProjectRole = ProjectRole.ARCHITECT

    def permissions(self) -> frozenset[ProjectPermission]:
        return _ROLE_PERMISSIONS.get(self.role, frozenset())

    def can(self, permission: ProjectPermission) -> bool:
        return permission in self.permissions()


def role_allows(role: ProjectRole, permission: ProjectPermission) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, frozenset())
