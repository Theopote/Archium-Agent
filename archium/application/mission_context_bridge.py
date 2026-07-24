"""Bridge mission fields into design-stage generation context."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import PlanningSessionRepository

_MISSION_CONTEXT_HEADER = "【任务理解语境】"


def resolve_project_mission(
    session: Session,
    project_id: UUID,
    *,
    presentation_id: UUID | None = None,
) -> ProjectMission | None:
    """Resolve the active mission for a project or linked presentation."""
    missions = MissionRepository(session)
    if presentation_id is not None:
        planning = PlanningSessionRepository(session).get_by_presentation_id(presentation_id)
        if planning is not None and planning.current_mission_id is not None:
            return missions.get_mission(planning.current_mission_id)
    listed = missions.list_missions_by_project(project_id)
    return listed[0] if listed else None


def merge_mission_project_context(
    base_context: str,
    mission: ProjectMission | None,
) -> str:
    """Append mission.project_context when it is not already present."""
    if mission is None:
        return base_context
    supplement = mission.project_context.strip()
    if not supplement:
        return base_context
    base = base_context.strip()
    if supplement in base or _MISSION_CONTEXT_HEADER in base:
        return base_context
    if not base:
        return f"{_MISSION_CONTEXT_HEADER}\n{supplement}"
    return f"{base}\n\n{_MISSION_CONTEXT_HEADER}\n{supplement}"
