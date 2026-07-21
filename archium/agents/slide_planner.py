"""Generate slide plans from storylines."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_retrieval_query_from_storyline,
    resolve_design_context_bundle,
    slides_from_plan,
    to_json,
)
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_lineage import apply_slide_lineage
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.outline import OutlinePlan
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
        outline: OutlinePlan | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        version: int = 1,
        replace_existing: bool = True,
    ) -> list[SlideSpec]:
        if replace_existing:
            existing = self._presentations.list_slides(brief.presentation_id)
            if existing:
                SlideHistoryService(self._session).archive_slides_before_regeneration(existing)
            self._presentations.delete_slides_for_presentation(brief.presentation_id)
        else:
            existing = self._presentations.list_slides(brief.presentation_id)

        context_bundle = resolve_design_context_bundle(
            self._session,
            project_id,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
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
                    outline_json=to_json(outline) if outline is not None else None,
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
        if existing:
            apply_slide_lineage(slides, existing)
        saved: list[SlideSpec] = []
        history = SlideHistoryService(self._session)
        for slide in slides:
            saved.append(self._presentations.save_slide(slide))
            history.record_snapshot(saved[-1], RevisionSource.GENERATED)
        return saved
