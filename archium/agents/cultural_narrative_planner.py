"""Generate cultural narrative plans for heritage village projects."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import build_project_context, build_retrieval_query_from_brief, to_json
from archium.application.artifact_history_service import CulturalNarrativeHistoryService
from archium.application.artifact_lineage import apply_cultural_narrative_lineage
from archium.application.cultural_narrative_service import (
    is_cultural_village_scenario,
    narrative_fallback_from_brief,
    narrative_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import CulturalNarrativePlanDraft
from archium.prompts.cultural_narrative import (
    CULTURAL_NARRATIVE_SYSTEM_PROMPT,
    build_cultural_narrative_user_prompt,
)


class CulturalNarrativePlanner:
    """Generate project-scoped CulturalNarrativePlan before Storyline."""

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
        self._history = CulturalNarrativeHistoryService(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        version: int | None = None,
    ) -> CulturalNarrativePlan | None:
        if not is_cultural_village_scenario(brief=brief):
            return None

        previous_plans = self._projects.list_cultural_narratives(project_id)
        previous = previous_plans[0] if previous_plans else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        if not self._settings.llm_configured:
            plan = narrative_fallback_from_brief(brief, project_id=project_id, version=version)
            return self._persist(plan, version, previous)

        project_context = build_project_context(
            self._session,
            project_id,
            query=build_retrieval_query_from_brief(brief),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=CULTURAL_NARRATIVE_SYSTEM_PROMPT,
                user_prompt=build_cultural_narrative_user_prompt(
                    project_context=project_context,
                    brief_json=to_json(brief),
                ),
                temperature=0.35,
            ),
            CulturalNarrativePlanDraft,
        )
        plan = narrative_from_draft(draft, project_id=project_id, version=version)
        if not plan.central_story.strip():
            plan = narrative_fallback_from_brief(brief, project_id=project_id, version=version)

        return self._persist(plan, version, previous)

    def _persist(
        self,
        plan: CulturalNarrativePlan,
        version: int,
        previous: CulturalNarrativePlan | None,
    ) -> CulturalNarrativePlan:
        plan.version = version
        apply_cultural_narrative_lineage(plan, previous)
        saved = self._projects.save_cultural_narrative(plan)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)
        self._projects.set_current_cultural_narrative(saved.project_id, saved.id)
        return saved
