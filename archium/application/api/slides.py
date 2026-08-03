"""/slides — slide specs + presentation document facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository


class SlidesApi:
    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._presentations = PresentationRepository(session)

    def get_presentation(self, presentation_id: UUID) -> Presentation | None:
        return self._presentations.get_presentation(presentation_id)

    def list_for_presentation(self, presentation_id: UUID) -> list[SlideSpec]:
        return self._presentations.list_slides(presentation_id)

    def get(self, slide_id: UUID) -> SlideSpec | None:
        return self._presentations.get_slide(slide_id)

    def save(self, slide: SlideSpec) -> SlideSpec:
        return self._presentations.save_slide(slide)

    def delete(self, slide_id: UUID) -> None:
        self._presentations.delete_slide(slide_id)

    def list_briefs(self, presentation_id: UUID) -> list[PresentationBrief]:
        return self._presentations.list_briefs(presentation_id)

    def get_brief(self, brief_id: UUID) -> PresentationBrief | None:
        return self._presentations.get_brief(brief_id)

    def list_outlines(self, presentation_id: UUID) -> list[OutlinePlan]:
        return self._presentations.list_outlines(presentation_id)

    def get_outline(self, outline_id: UUID) -> OutlinePlan | None:
        return self._presentations.get_outline(outline_id)
