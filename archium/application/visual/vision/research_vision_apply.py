"""Apply Research→Vision seeds onto ConceptDirection visual_prompt (Visual seat)."""

from __future__ import annotations

from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.concept_direction import ConceptDirection
from archium.domain.research_vision import ResearchVisionBundle
from archium.infrastructure.database.repositories import ConceptDirectionRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="research_vision_apply")


def apply_vision_bundles_to_directions(
    session: SessionLike,
    project_id: UUID,
    bundles: list[ResearchVisionBundle],
    *,
    mission_id: UUID | None = None,
    only_if_empty: bool = True,
    limit: int = 3,
) -> list[ConceptDirection]:
    """Write primary concept-sketch seeds onto open concept directions.

    Does not generate pixels. Skips archived directions when listing.
    """
    session = session_of(session)
    if not bundles:
        return []
    repo = ConceptDirectionRepository(session)
    if mission_id is not None:
        directions = repo.list_by_mission(mission_id, include_archived=False)
    else:
        directions = repo.list_by_project(project_id, include_archived=False)
    directions.sort(key=lambda d: (d.sort_order, str(d.id)))
    updated: list[ConceptDirection] = []
    for direction, bundle in zip(directions[:limit], bundles[:limit], strict=False):
        prompt = bundle.primary_visual_prompt()
        if prompt is None or prompt.is_empty():
            continue
        if only_if_empty and direction.visual_prompt is not None and not direction.visual_prompt.is_empty():
            continue
        direction.visual_prompt = prompt
        if bundle.spatial_translation.strip() and not direction.spatial_strategy.strip():
            direction.spatial_strategy = bundle.spatial_translation.strip()[:500]
        if bundle.insight.strip() and not direction.experience_focus.strip():
            direction.experience_focus = bundle.insight.strip()[:300]
        direction.touch()
        updated.append(repo.update(direction))
        logger.info(
            "Applied research vision seed to direction %s from topic=%s",
            direction.id,
            bundle.topic,
        )
    if updated:
        session.flush()
    return updated
