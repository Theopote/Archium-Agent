"""Generate editable outline plans from storylines."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_project_context,
    build_retrieval_query_from_storyline,
    to_json,
)
from archium.application.artifact_history_service import OutlineHistoryService
from archium.application.artifact_lineage import apply_outline_lineage
from archium.application.outline_service import (
    infer_audience_mode,
    merge_template_with_storyline,
    outline_from_draft,
)
from archium.application.outline_templates import detect_scenario_template, template_sections
from archium.config.settings import Settings, get_settings
from archium.domain.enums import OutlineAudienceMode, RevisionSource
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import OutlinePlanDraft
from archium.prompts.outline_planning import (
    OUTLINE_PLAN_SYSTEM_PROMPT,
    build_outline_plan_user_prompt,
)


class OutlinePlanner:
    """Generate OutlinePlan between Storyline and SlideSpec."""

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
        self._history = OutlineHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        version: int | None = None,
        audience_mode: OutlineAudienceMode | None = None,
    ) -> OutlinePlan:
        previous_outlines = self._presentations.list_outlines(brief.presentation_id)
        previous = previous_outlines[0] if previous_outlines else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        mode = audience_mode or infer_audience_mode(brief.audience, brief.purpose)
        fallback = merge_template_with_storyline(brief, storyline)

        if not self._settings.llm_configured:
            saved = self._persist(fallback, brief, version, previous)
            return saved

        template_key = detect_scenario_template(
            required_sections=list(brief.required_sections),
            purpose=brief.purpose,
            audience=brief.audience,
        )
        template_hint = None
        if template_key is not None:
            template_hint = "\n".join(
                f"- {section.title}: {section.key_message}"
                for section in template_sections(template_key)[:12]
            )

        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_storyline(brief, storyline),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=OUTLINE_PLAN_SYSTEM_PROMPT,
                user_prompt=build_outline_plan_user_prompt(
                    project_context=project_context,
                    brief_json=to_json(brief),
                    storyline_json=to_json(storyline),
                    target_slide_count=brief.target_slide_count,
                    audience_mode=mode.value,
                    template_hint=template_hint,
                ),
                temperature=0.35,
            ),
            OutlinePlanDraft,
        )
        outline = outline_from_draft(
            draft,
            presentation_id=brief.presentation_id,
            version=version,
        )
        outline.audience_mode = mode
        if not outline.sections:
            outline.sections = list(fallback.sections)

        saved = self._persist(outline, brief, version, previous)
        return saved

    def _persist(
        self,
        outline: OutlinePlan,
        brief: PresentationBrief,
        version: int,
        previous: OutlinePlan | None,
    ) -> OutlinePlan:
        outline.version = version
        apply_outline_lineage(outline, previous)
        saved = self._presentations.save_outline(outline)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_outline_id = saved.id
            self._presentations.update_presentation(presentation)
        return saved
