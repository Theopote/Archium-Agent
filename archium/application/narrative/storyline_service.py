"""Storyline generation — Application Service owns persist."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application._helpers import (
    build_retrieval_query_from_brief,
    resolve_design_context_text,
)
from archium.agents.narrative_architect import NarrativeArchitect
from archium.application.artifact_history_service import StorylineHistoryService
from archium.application.artifact_lineage import apply_storyline_lineage
from archium.application.mission_context_bridge import (
    enrich_mission_generation_context,
    resolve_project_mission,
)
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider


class StorylineService:
    """Orchestrate Storyline proposal + persistence (not an Agent)."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._history = StorylineHistoryService(session)
        self._architect = NarrativeArchitect(llm, settings=self._settings)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        version: int | None = None,
    ) -> Storyline:
        previous_storylines = self._presentations.list_storylines(brief.presentation_id)
        previous = previous_storylines[0] if previous_storylines else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        project_context = resolve_design_context_text(
            self._session,
            project_id,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        mission = resolve_project_mission(
            self._session,
            project_id,
            presentation_id=brief.presentation_id,
        )
        project_context = enrich_mission_generation_context(
            self._session,
            project_context,
            mission,
        )
        narrative_mode = mission.narrative_mode if mission is not None else None
        design_intent_block = ""
        if mission is not None and mission.design_intent is not None:
            design_intent_block = mission.design_intent.to_prompt_block()

        storyline = self._architect.propose(
            brief,
            project_context=project_context,
            version=version,
            cultural_narrative=cultural_narrative,
            renovation_issue_map=renovation_issue_map,
            narrative_mode=narrative_mode,
            design_intent_block=design_intent_block,
        )
        apply_storyline_lineage(storyline, previous)
        saved = self._presentations.save_storyline(storyline)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_storyline_id = saved.id
            self._presentations.update_presentation(presentation)
        return saved
