"""Bridge mission fields into design-stage generation context."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    PlanningSessionRepository,
)

_MISSION_CONTEXT_HEADER = "【任务理解语境】"
_DESIGN_INTENT_HEADER = "【设计使命】"
_CONCEPT_DIRECTION_HEADER = "【当前概念方向】"


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


def resolve_selected_concept_direction(
    session: Session,
    mission_id: UUID,
) -> ConceptDirection | None:
    """Return the selected concept direction draft for a mission, if any."""
    for item in ConceptDirectionRepository(session).list_by_mission(mission_id):
        if item.status == ConceptDirectionStatus.SELECTED:
            return item
    return None


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


def merge_design_intent_context(
    base_context: str,
    mission: ProjectMission | None,
) -> str:
    """Append design_intent prompt block when present."""
    if mission is None or mission.design_intent is None:
        return base_context
    block = mission.design_intent.to_prompt_block().strip()
    if not block:
        return base_context
    base = base_context.strip()
    if _DESIGN_INTENT_HEADER in base or block in base:
        return base_context
    if not base:
        return f"{_DESIGN_INTENT_HEADER}\n{block}"
    return f"{base}\n\n{_DESIGN_INTENT_HEADER}\n{block}"


def merge_concept_direction_context(
    base_context: str,
    direction: ConceptDirection | None,
) -> str:
    """Append the selected concept direction block when present."""
    if direction is None:
        return base_context
    block = direction.to_prompt_block().strip()
    if not block:
        return base_context
    base = base_context.strip()
    if _CONCEPT_DIRECTION_HEADER in base or block in base:
        return base_context
    if not base:
        return f"{_CONCEPT_DIRECTION_HEADER}\n{block}"
    return f"{base}\n\n{_CONCEPT_DIRECTION_HEADER}\n{block}"


def enrich_mission_generation_context(
    session: Session,
    base_context: str,
    mission: ProjectMission | None,
) -> str:
    """Merge mission project_context, design_intent, and selected concept direction."""
    context = merge_mission_project_context(base_context, mission)
    context = merge_design_intent_context(context, mission)
    if mission is None:
        return context
    direction = resolve_selected_concept_direction(session, mission.id)
    return merge_concept_direction_context(context, direction)
