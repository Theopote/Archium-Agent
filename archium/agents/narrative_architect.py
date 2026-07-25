"""Generate storylines — LLM proposal only (no Session)."""

from __future__ import annotations

from uuid import UUID

from archium.application._helpers import storyline_from_draft, to_json
from archium.application.cultural_narrative_service import format_narrative_for_prompt
from archium.application.renovation_issue_service import format_issue_map_for_prompt
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.renovation_issue import RenovationIssueMap
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import StorylineDraft
from archium.prompts.storyline import STORYLINE_SYSTEM_PROMPT, build_storyline_user_prompt


class NarrativeArchitect:
    """Narrative planner: propose a Storyline from brief + context text.

    Does **not** read/write the database. Persistence belongs to ``StorylineService``.
    """

    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings or get_settings()

    def propose(
        self,
        brief: PresentationBrief,
        *,
        project_context: str,
        version: int = 1,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        narrative_mode: ArchitecturalNarrativeMode | None = None,
        design_intent_block: str = "",
    ) -> Storyline:
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
                    design_intent_block=design_intent_block or None,
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
        return storyline
