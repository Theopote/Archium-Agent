"""Renovation issue map — LLM proposal only (no Session)."""

from __future__ import annotations

from uuid import UUID

from archium.agents._helpers import to_json
from archium.application.renovation_issue_service import (
    is_renovation_scenario,
    issue_map_fallback_from_brief,
    issue_map_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import RenovationIssueMapDraft
from archium.prompts.renovation_issue import (
    RENOVATION_ISSUE_MAP_SYSTEM_PROMPT,
    build_renovation_issue_map_user_prompt,
)


class RenovationIssueMapPlanner:
    """Narrative planner: propose RenovationIssueMap (no DB)."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings or get_settings()

    def should_run(self, brief: PresentationBrief) -> bool:
        return is_renovation_scenario(brief=brief)

    def propose(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        project_context: str,
        version: int = 1,
    ) -> RenovationIssueMap:
        if not self._settings.llm_configured:
            return issue_map_fallback_from_brief(
                brief, project_id=project_id, version=version
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
            plan = issue_map_fallback_from_brief(
                brief, project_id=project_id, version=version
            )
        return plan
