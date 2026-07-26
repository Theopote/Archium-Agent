"""Outline plan generation — Application Service owns persist."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.outline_planner import OutlinePlanner
from archium.application._helpers import (
    build_retrieval_query_from_storyline,
    resolve_design_context_text,
)
from archium.application.artifact_history_service import OutlineHistoryService
from archium.application.artifact_lineage import apply_outline_lineage
from archium.application.mission_context_bridge import (
    enrich_mission_generation_context,
    resolve_project_mission,
)
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import OutlineAudienceMode, RevisionSource
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.slide_asset_binding import SlideAssetBinding
from archium.domain.slide_intent import SlideIntent
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider


class OutlinePlanService:
    """Orchestrate Outline proposal + persistence (not an Agent)."""

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
        self._history = OutlineHistoryService(session)
        self._planner = OutlinePlanner(llm, settings=self._settings)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        version: int | None = None,
        audience_mode: OutlineAudienceMode | None = None,
        page_intents: list[SlideIntent] | None = None,
        page_asset_bindings: list[SlideAssetBinding] | None = None,
    ) -> OutlinePlan:
        previous_outlines = self._presentations.list_outlines(brief.presentation_id)
        previous = previous_outlines[0] if previous_outlines else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        project_context = resolve_design_context_text(
            self._session,
            project_id,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            query=build_retrieval_query_from_storyline(brief, storyline),
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

        outline = self._planner.propose(
            brief,
            storyline,
            project_context=project_context,
            version=version,
            audience_mode=audience_mode,
            cultural_narrative=cultural_narrative,
            renovation_issue_map=renovation_issue_map,
            page_intents=page_intents,
            page_asset_bindings=page_asset_bindings,
            previous=previous,
        )
        apply_outline_lineage(outline, previous)
        saved = self._presentations.save_outline(outline)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_outline_id = saved.id
            self._presentations.update_presentation(presentation)
        return saved
