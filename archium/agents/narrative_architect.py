"""Generate storylines from briefs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import build_project_context, storyline_from_draft, to_json
from archium.domain.presentation import PresentationBrief, Storyline
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import StorylineDraft
from archium.prompts.storyline import STORYLINE_SYSTEM_PROMPT, build_storyline_user_prompt


class NarrativeArchitect:
    """Generate chapter-based storylines."""

    def __init__(self, session: Session, llm: LLMProvider) -> None:
        self._session = session
        self._llm = llm
        self._presentations = PresentationRepository(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> Storyline:
        if version is None:
            version = self._next_storyline_version(brief.presentation_id)

        project_context = build_project_context(self._session, project_id)
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
        saved = self._presentations.save_storyline(storyline)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_storyline_id = saved.id
            self._presentations.update_presentation(presentation)

        return saved

    def _next_storyline_version(self, presentation_id: UUID) -> int:
        storylines = self._presentations.list_storylines(presentation_id)
        if not storylines:
            return 1
        return max(item.version for item in storylines) + 1
