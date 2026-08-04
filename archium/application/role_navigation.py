"""Role-aware navigation hints (Topic 08 C3 / COLLAB-005)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.access import (
    LOCAL_ACTOR_ID,
    ProjectPermission,
    ProjectRole,
)


@dataclass(frozen=True)
class RoleNavigationHint:
    """Product chrome guidance for the current actor on a project."""

    role: ProjectRole | None
    primary_page_key: str
    message: str
    can_edit: bool
    can_export: bool
    can_review: bool

    @property
    def is_read_leaning(self) -> bool:
        return self.role in {ProjectRole.CLIENT, ProjectRole.REVIEWER}


def resolve_role_navigation(
    session: SessionLike,
    project_id: UUID,
    *,
    actor_id: str | None = None,
    slide_count: int = 0,
    presentation_stage_id: str = "materials",
) -> RoleNavigationHint:
    """Map membership role → primary page + soft chrome message."""
    session = session_of(session)
    from archium.application.project_access_service import ProjectAccessService

    resolved = (actor_id or "").strip() or LOCAL_ACTOR_ID
    access = ProjectAccessService(session)
    member = access.get_member(project_id, resolved)
    if member is None and resolved == LOCAL_ACTOR_ID:
        member = access.ensure_default_owner(project_id)

    role = member.role if member is not None else None
    can_edit = access.can(project_id, resolved, ProjectPermission.EDIT)
    can_export = access.can(project_id, resolved, ProjectPermission.EXPORT)
    can_review = access.can(project_id, resolved, ProjectPermission.REVIEW)

    if role == ProjectRole.CLIENT:
        page = "deliver" if slide_count > 0 else "materials"
        return RoleNavigationHint(
            role=role,
            primary_page_key=page,
            message="甲方视角：以资料与交付审阅为主；不能改方向或生成稿。",
            can_edit=can_edit,
            can_export=can_export,
            can_review=can_review,
        )
    if role == ProjectRole.REVIEWER:
        page = "deliver" if slide_count > 0 else "edit"
        if slide_count <= 0 and presentation_stage_id in {"materials", "outline"}:
            page = presentation_stage_id
        return RoleNavigationHint(
            role=role,
            primary_page_key=page,
            message="审阅视角：可看稿、批注与导出；不宜改 Mission / 大纲生成。",
            can_edit=can_edit,
            can_export=can_export,
            can_review=can_review,
        )

    # Owner / Architect / unknown → keep presentation-stage heuristic
    return RoleNavigationHint(
        role=role,
        primary_page_key=presentation_stage_id,
        message="",
        can_edit=can_edit,
        can_export=can_export,
        can_review=can_review,
    )


_ROLE_ZH = {
    ProjectRole.OWNER: "负责人",
    ProjectRole.ARCHITECT: "建筑师",
    ProjectRole.REVIEWER: "审阅者",
    ProjectRole.CLIENT: "甲方",
}


def role_label(role: ProjectRole | None) -> str:
    if role is None:
        return "访客"
    return _ROLE_ZH.get(role, role.value)
