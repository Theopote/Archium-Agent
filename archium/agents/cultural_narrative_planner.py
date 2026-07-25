"""Cultural narrative — LLM proposal only (no Session)."""

from __future__ import annotations

from uuid import UUID

from archium.application._helpers import to_json
from archium.application.cultural_narrative_service import (
    is_cultural_village_scenario,
    narrative_fallback_from_brief,
    narrative_from_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import CulturalNarrativePlanDraft
from archium.prompts.cultural_narrative import (
    CULTURAL_NARRATIVE_SYSTEM_PROMPT,
    build_cultural_narrative_user_prompt,
)


class CulturalNarrativePlanner:
    """Narrative planner: propose CulturalNarrativePlan (no DB)."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings or get_settings()

    def should_run(self, brief: PresentationBrief) -> bool:
        return is_cultural_village_scenario(brief=brief)

    def propose(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        project_context: str,
        version: int = 1,
    ) -> CulturalNarrativePlan:
        if not self._settings.llm_configured:
            return narrative_fallback_from_brief(
                brief, project_id=project_id, version=version
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
            plan = narrative_fallback_from_brief(
                brief, project_id=project_id, version=version
            )
        return plan
