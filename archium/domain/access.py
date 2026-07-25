"""Project access control — minimal multi-role foundation (single-user ready)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now

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


class ProjectInvite(IdentifiedModel, TimestampedModel):
    """Shareable invite code — no email/OAuth required for local multi-seat."""

    project_id: UUID
    code: str = Field(min_length=6, max_length=40)
    role: ProjectRole = ProjectRole.REVIEWER
    created_by: str = Field(default=LOCAL_ACTOR_ID, max_length=200)
    expires_at: datetime | None = None
    max_uses: int = Field(default=5, ge=1, le=100)
    use_count: int = Field(default=0, ge=0)
    revoked: bool = False
    label: str = Field(default="", max_length=200)

    def is_redeemable(self, *, now: datetime | None = None) -> bool:
        if self.revoked:
            return False
        if self.use_count >= self.max_uses:
            return False
        if self.expires_at is not None:
            from datetime import UTC

            stamp = now or utc_now()
            expires = self.expires_at
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if stamp >= expires:
                return False
        return True


def role_allows(role: ProjectRole, permission: ProjectPermission) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, frozenset())
