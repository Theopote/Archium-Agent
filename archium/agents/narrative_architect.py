"""Generate storylines from briefs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_project_context,
    build_retrieval_query_from_brief,
    storyline_from_draft,
    to_json,
)
from archium.application.artifact_history_service import StorylineHistoryService
from archium.application.artifact_lineage import apply_storyline_lineage
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief, Storyline
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import StorylineDraft
from archium.prompts.storyline import STORYLINE_SYSTEM_PROMPT, build_storyline_user_prompt


class NarrativeArchitect:
    """Generate chapter-based storylines."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._history = StorylineHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> Storyline:
        previous_storylines = self._presentations.list_storylines(brief.presentation_id)
        previous = previous_storylines[0] if previous_storylines else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=STORYLINE_SYSTEM_PROMPT,
                user_prompt=build_storyline_user_prompt(
                    project_context=project_context,
                    brief_json=to_json(brief),
                ),
                temperature=0.4,
            ),
            StorylineDraft,
        )
        storyline = storyline_from_draft(
            draft,
            presentation_id=brief.presentation_id,
            version=version,
        )
        apply_storyline_lineage(storyline, previous)
        saved = self._presentations.save_storyline(storyline)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_storyline_id = saved.id
            self._presentations.update_presentation(presentation)

        return saved
