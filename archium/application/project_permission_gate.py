"""Unified project permission gate (Topic 08 C1–C2 / APP-028 / COLLAB-001)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.project_access_service import ProjectAccessService
from archium.domain.access import LOCAL_ACTOR_ID, ProjectMember, ProjectPermission


def resolve_actor_id(actor_id: str | None = None) -> str:
    """Normalize actor id; blank → ``local-user``."""
    text = (actor_id or "").strip()
    return text[:200] if text else LOCAL_ACTOR_ID


def require_project_permission(
    session: SessionLike,
    project_id: UUID,
    permission: ProjectPermission,
    *,
    actor_id: str | None = None,
) -> ProjectMember | None:
    """Require ``permission`` for actor. Raises AccessDeniedError."""
    session = session_of(session)
    resolved = resolve_actor_id(actor_id)
    return ProjectAccessService(session).require(project_id, resolved, permission)


def actor_can(
    session: SessionLike,
    project_id: UUID,
    permission: ProjectPermission,
    *,
    actor_id: str | None = None,
) -> bool:
    session = session_of(session)
    resolved = resolve_actor_id(actor_id)
    return ProjectAccessService(session).can(project_id, resolved, permission)
