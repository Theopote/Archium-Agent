"""/storyline — narrative storyline facade."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.presentation import PresentationBrief, Storyline
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider


class StorylineApi:
    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._presentations = PresentationRepository(session)

    def list_for_presentation(self, presentation_id: UUID) -> list[Storyline]:
        return self._presentations.list_storylines(presentation_id)

    def get(self, storyline_id: UUID) -> Storyline | None:
        return self._presentations.get_storyline(storyline_id)

    def generate(
        self,
        llm: LLMProvider,
        project_id: UUID,
        brief: PresentationBrief,
        **kwargs: Any,
    ) -> Storyline:
        from archium.application.narrative.storyline_service import StorylineService

        return StorylineService(self._session, llm).generate(project_id, brief, **kwargs)
