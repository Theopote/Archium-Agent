"""Generate storylines from briefs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_retrieval_query_from_brief,
    resolve_design_context_text,
    storyline_from_draft,
    to_json,
)
from archium.application.artifact_history_service import StorylineHistoryService
from archium.application.artifact_lineage import apply_storyline_lineage
from archium.application.cultural_narrative_service import format_narrative_for_prompt
from archium.application.renovation_issue_service import format_issue_map_for_prompt
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    PlanningSessionRepository,
    PresentationRepository,
)
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
        self._missions = MissionRepository(session)
        self._planning_sessions = PlanningSessionRepository(session)
        self._history = StorylineHistoryService(session)

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
        missions = self._missions.list_missions_by_project(project_id)
        mission = None
        planning = self._planning_sessions.get_by_presentation_id(brief.presentation_id)
        if planning is not None and planning.current_mission_id is not None:
            mission = self._missions.get_mission(planning.current_mission_id)
        if mission is None and missions:
            # Fallback for shortcut Brief paths without a planning session link.
            mission = missions[0]
        narrative_mode = mission.narrative_mode if mission is not None else None
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=STORYLINE_SYSTEM_PROMPT,
                user_prompt=build_storyline_user_prompt(
                    project_context=project_context,
                    brief_json=to_json(brief),
                    narrative_json=format_narrative_for_prompt(cultural_narrative)
                    if cultural_narrative is not None
                    else None,
                    issue_map_json=format_issue_map_for_prompt(renovation_issue_map)
                    if renovation_issue_map is not None
                    else None,
                    narrative_mode=narrative_mode,
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
        if narrative_mode is not None:
            storyline.narrative_pattern = narrative_mode.value
        apply_storyline_lineage(storyline, previous)
        saved = self._presentations.save_storyline(storyline)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(brief.presentation_id)
        if presentation is not None:
            presentation.current_storyline_id = saved.id
            self._presentations.update_presentation(presentation)

        return saved
