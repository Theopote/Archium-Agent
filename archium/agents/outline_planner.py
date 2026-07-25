"""Generate outline plans — LLM proposal only (no Session)."""

from __future__ import annotations

from archium.application._helpers import to_json
from archium.application.cultural_narrative_service import format_narrative_for_prompt
from archium.application.outline_service import (
    infer_audience_mode,
    merge_template_with_storyline,
    outline_from_draft,
)
from archium.application.outline_templates import detect_scenario_template, template_sections
from archium.application.renovation_issue_service import format_issue_map_for_prompt
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import OutlineAudienceMode
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.slide_asset_binding import SlideAssetBinding
from archium.domain.slide_intent import SlideIntent
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import OutlinePlanDraft
from archium.prompts.outline_planning import (
    OUTLINE_PLAN_SYSTEM_PROMPT,
    build_outline_plan_user_prompt,
)


class OutlinePlanner:
    """Narrative planner: propose OutlinePlan from storyline + context text.

    Does **not** read/write the database. Persistence belongs to ``OutlinePlanService``.
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
        storyline: Storyline,
        *,
        project_context: str,
        version: int = 1,
        audience_mode: OutlineAudienceMode | None = None,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        page_intents: list[SlideIntent] | None = None,
        page_asset_bindings: list[SlideAssetBinding] | None = None,
        previous: OutlinePlan | None = None,
    ) -> OutlinePlan:
        mode = audience_mode or infer_audience_mode(brief.audience, brief.purpose)
        fallback = merge_template_with_storyline(brief, storyline)

        if not self._settings.llm_configured:
            outline = fallback.model_copy(deep=True)
            outline.version = version
            outline.audience_mode = mode
            _attach_page_intents(outline, page_intents=page_intents, previous=previous)
            _attach_page_asset_bindings(
                outline, page_asset_bindings=page_asset_bindings, previous=previous
            )
            return outline

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
                    narrative_json=format_narrative_for_prompt(cultural_narrative)
                    if cultural_narrative is not None
                    else None,
                    issue_map_json=format_issue_map_for_prompt(renovation_issue_map)
                    if renovation_issue_map is not None
                    else None,
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
        _attach_page_intents(outline, page_intents=page_intents, previous=previous)
        _attach_page_asset_bindings(
            outline, page_asset_bindings=page_asset_bindings, previous=previous
        )
        return outline


def _attach_page_intents(
    outline: OutlinePlan,
    *,
    page_intents: list[SlideIntent] | None,
    previous: OutlinePlan | None,
) -> None:
    if page_intents is not None:
        outline.page_intents = list(page_intents)
    elif previous is not None and previous.page_intents:
        outline.page_intents = list(previous.page_intents)


def _attach_page_asset_bindings(
    outline: OutlinePlan,
    *,
    page_asset_bindings: list[SlideAssetBinding] | None,
    previous: OutlinePlan | None,
) -> None:
    if page_asset_bindings is not None:
        outline.page_asset_bindings = list(page_asset_bindings)
    elif previous is not None and previous.page_asset_bindings:
        outline.page_asset_bindings = list(previous.page_asset_bindings)
