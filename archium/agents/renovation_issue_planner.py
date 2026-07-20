"""Generate renovation issue maps for retrofit projects."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import build_project_context, build_retrieval_query_from_brief, to_json
from archium.application.artifact_history_service import RenovationIssueMapHistoryService
from archium.application.artifact_lineage import apply_renovation_issue_map_lineage
from archium.application.renovation_issue_service import (
    is_renovation_scenario,
    issue_map_fallback_from_brief,
    issue_map_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import RenovationIssueMapDraft
from archium.prompts.renovation_issue import (
    RENOVATION_ISSUE_MAP_SYSTEM_PROMPT,
    build_renovation_issue_map_user_prompt,
)


class RenovationIssueMapPlanner:
    """Generate project-scoped RenovationIssueMap before Storyline."""

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
        self._projects = ProjectRepository(session)
        self._history = RenovationIssueMapHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> RenovationIssueMap | None:
        if not is_renovation_scenario(brief=brief):
            return None

        previous_maps = self._projects.list_renovation_issue_maps(project_id)
        previous = previous_maps[0] if previous_maps else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        if not self._settings.llm_configured:
            plan = issue_map_fallback_from_brief(brief, project_id=project_id, version=version)
            return self._persist(plan, version, previous)

        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=RENOVATION_ISSUE_MAP_SYSTEM_PROMPT,
                user_prompt=build_renovation_issue_map_user_prompt(
                    project_context=project_context,
                    brief_json=to_json(brief),
                ),
                temperature=0.35,
            ),
            RenovationIssueMapDraft,
        )
        plan = issue_map_from_draft(draft, project_id=project_id, version=version)
        if not plan.building_summary.strip():
            plan = issue_map_fallback_from_brief(brief, project_id=project_id, version=version)

        return self._persist(plan, version, previous)

    def _persist(
        self,
        plan: RenovationIssueMap,
        version: int,
        previous: RenovationIssueMap | None,
    ) -> RenovationIssueMap:
        plan.version = version
        apply_renovation_issue_map_lineage(plan, previous)
        saved = self._projects.save_renovation_issue_map(plan)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_renovation_issue_map(saved.project_id, saved.id)
        return saved
