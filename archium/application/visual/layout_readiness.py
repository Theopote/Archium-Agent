"""Layout / visual readiness helpers for export and delivery gates."""

from __future__ import annotations

from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import LayoutPlanRepository


def presentation_has_visual_layout(session: SessionLike, presentation_id: UUID) -> bool:
    """Return True when every slide has a persisted LayoutPlan."""
    session = session_of(session)
    presentations = PresentationRepository(session)
    plans = LayoutPlanRepository(session)
    slides = presentations.list_slides(presentation_id)
    if not slides:
        return False
    for slide in slides:
        if slide.layout_plan_id is None:
            return False
        if plans.get(slide.layout_plan_id) is None:
            return False
    return True
