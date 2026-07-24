"""Bridge mission fields into design-stage generation context."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ExplorationSessionRepository,
    PlanningSessionRepository,
    VisualConceptBriefRepository,
)

_MISSION_CONTEXT_HEADER = "【任务理解语境】"
_DESIGN_INTENT_HEADER = "【设计使命】"
_CONCEPT_DIRECTION_HEADER = "【当前概念方向】"
_VISUAL_CONCEPT_HEADER = "【视觉概念简报】"


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
    """Return the selected concept direction for a mission, if any.

    Prefers SELECTED rows on the mission; if none, falls back to the project's
    latest ExplorationSession.selected_direction_id (pre-mission or just-committed).
    """
    directions = ConceptDirectionRepository(session)
    for item in directions.list_by_mission(mission_id):
        if item.status == ConceptDirectionStatus.SELECTED:
            return item

    mission = MissionRepository(session).get_mission(mission_id)
    if mission is None:
        return None
    exploration = ExplorationSessionRepository(session).get_latest_for_project(mission.project_id)
    if exploration is None or exploration.selected_direction_id is None:
        return None
    selected = directions.get(exploration.selected_direction_id)
    if selected is None:
        return None
    if selected.mission_id is not None and selected.mission_id != mission_id:
        return None
    return selected


def resolve_visual_concept_brief_for_direction(
    session: Session,
    concept_direction_id: UUID,
) -> VisualConceptBrief | None:
    """Return the latest visual concept brief for a direction, if any."""
    return VisualConceptBriefRepository(session).get_latest_for_direction(concept_direction_id)


def resolve_visual_concept_brief_for_mission(
    session: Session,
    mission_id: UUID,
) -> VisualConceptBrief | None:
    """Return the latest visual brief for the selected concept direction, if any."""
    direction = resolve_selected_concept_direction(session, mission_id)
    if direction is None:
        return None
    return resolve_visual_concept_brief_for_direction(session, direction.id)


def resolve_visual_concept_brief_for_presentation(
    session: Session,
    presentation_id: UUID,
) -> VisualConceptBrief | None:
    """Resolve selected-direction visual brief via presentation → project → mission."""
    from archium.infrastructure.database.repositories import PresentationRepository

    presentation = PresentationRepository(session).get_presentation(presentation_id)
    if presentation is None:
        return None
    mission = resolve_project_mission(
        session,
        presentation.project_id,
        presentation_id=presentation_id,
    )
    if mission is None:
        return None
    return resolve_visual_concept_brief_for_mission(session, mission.id)


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


def merge_visual_concept_brief_context(
    base_context: str,
    brief: VisualConceptBrief | None,
) -> str:
    """Append the visual concept brief block when present."""
    if brief is None:
        return base_context
    block = brief.to_prompt_block().strip()
    if not block:
        return base_context
    base = base_context.strip()
    if _VISUAL_CONCEPT_HEADER in base or block in base:
        return base_context
    if not base:
        return f"{_VISUAL_CONCEPT_HEADER}\n{block}"
    return f"{base}\n\n{_VISUAL_CONCEPT_HEADER}\n{block}"


def enrich_mission_generation_context(
    session: Session,
    base_context: str,
    mission: ProjectMission | None,
) -> str:
    """Merge mission, design_intent, selected direction, and its visual brief."""
    context = merge_mission_project_context(base_context, mission)
    context = merge_design_intent_context(context, mission)
    if mission is None:
        return context
    direction = resolve_selected_concept_direction(session, mission.id)
    context = merge_concept_direction_context(context, direction)
    if direction is None:
        return context
    brief = resolve_visual_concept_brief_for_direction(session, direction.id)
    return merge_visual_concept_brief_context(context, brief)
