"""Unified project permission gate (Topic 08 C1 / APP-028)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_access_service import ProjectAccessService
from archium.domain.access import LOCAL_ACTOR_ID, ProjectMember, ProjectPermission


def require_project_permission(
    session: Session,
    project_id: UUID,
    permission: ProjectPermission,
    *,
    actor_id: str | None = None,
) -> ProjectMember | None:
    """Require ``permission`` for actor (default session/local). Raises AccessDeniedError."""
    resolved = (actor_id or LOCAL_ACTOR_ID).strip() or LOCAL_ACTOR_ID
    return ProjectAccessService(session).require(project_id, resolved, permission)


def actor_can(
    session: Session,
    project_id: UUID,
    permission: ProjectPermission,
    *,
    actor_id: str | None = None,
) -> bool:
    resolved = (actor_id or LOCAL_ACTOR_ID).strip() or LOCAL_ACTOR_ID
    return ProjectAccessService(session).can(project_id, resolved, permission)
