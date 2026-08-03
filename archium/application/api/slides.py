"""/slides — slide specs facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository


class SlidesApi:
    def __init__(self, session: Session) -> None:
        self._presentations = PresentationRepository(session)

    def list_for_presentation(self, presentation_id: UUID) -> list[SlideSpec]:
        return self._presentations.list_slides(presentation_id)

    def get(self, slide_id: UUID) -> SlideSpec | None:
        return self._presentations.get_slide(slide_id)
