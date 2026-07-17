"""Generate slide plans from storylines."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_project_context_bundle,
    build_retrieval_query_from_storyline,
    slides_from_plan,
    to_json,
)
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import SlidePlanDraft
from archium.prompts.slide_planning import SLIDE_PLAN_SYSTEM_PROMPT, build_slide_plan_user_prompt


class SlidePlanner:
    """Generate SlideSpec lists."""

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

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        version: int = 1,
        replace_existing: bool = True,
    ) -> list[SlideSpec]:
        if replace_existing:
            self._presentations.delete_slides_for_presentation(brief.presentation_id)

        context_bundle = build_project_context_bundle(
            self._session,
            project_id,
            query=build_retrieval_query_from_storyline(brief, storyline),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=SLIDE_PLAN_SYSTEM_PROMPT,
                user_prompt=build_slide_plan_user_prompt(
                    project_context=context_bundle.text,
                    brief_json=to_json(brief),
                    storyline_json=to_json(storyline),
                    target_slide_count=brief.target_slide_count,
                ),
                temperature=0.5,
            ),
            SlidePlanDraft,
        )
        slides = slides_from_plan(
            draft,
            presentation_id=brief.presentation_id,
            session=self._session,
            context_bundle=context_bundle,
            project_id=project_id,
            settings=self._settings,
            version=version,
        )
        saved: list[SlideSpec] = []
        for slide in slides:
            saved.append(self._presentations.save_slide(slide))
        return saved
