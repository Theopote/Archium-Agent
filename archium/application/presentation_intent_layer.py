"""Build / ensure PresentationIntent and SlideRole / VisualStrategy (no new Agent)."""

from __future__ import annotations

from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import NarrativeStage, PresentationType, ServiceDepth
from archium.domain.presentation import PresentationBrief
from archium.domain.presentation_intent import (
    PresentationIntent,
    default_persuasion_for_type,
    default_visual_style_for_type,
    depth_from_service_depths,
    infer_audience_mode,
)
from archium.domain.project_mission import ProjectMission
from archium.domain.slide import SlideSpec
from archium.domain.slide_intent import SlideIntent
from archium.domain.slide_role import (
    resolve_slide_role,
    visual_strategy_from_role,
)


def presentation_intent_from_brief(brief: PresentationBrief) -> PresentationIntent:
    if brief.presentation_intent is not None and not brief.presentation_intent.is_empty():
        intent = brief.presentation_intent
        # Keep scalars as source of truth when set
        return intent.model_copy(
            update={
                "audience": intent.audience or brief.audience,
                "purpose": intent.purpose or brief.purpose,
                "key_message": intent.key_message or brief.core_message,
                "presentation_type": intent.presentation_type
                if intent.presentation_type != PresentationType.OTHER
                else brief.presentation_type,
            }
        )
    return PresentationIntent(
        audience=brief.audience,
        purpose=brief.purpose,
        key_message=brief.core_message,
        persuasion_strategy=default_persuasion_for_type(brief.presentation_type),
        visual_style=default_visual_style_for_type(brief.presentation_type),
        audience_mode=infer_audience_mode(brief.audience, brief.presentation_type),
        presentation_type=brief.presentation_type,
    )


def presentation_intent_from_request(
    request: PresentationRequest,
    *,
    service_depths: list[ServiceDepth] | None = None,
) -> PresentationIntent:
    if request.presentation_intent is not None and not request.presentation_intent.is_empty():
        return request.presentation_intent
    ptype = request.presentation_type
    return PresentationIntent(
        audience=request.audience,
        purpose=request.purpose,
        key_message=request.core_message or request.purpose,
        persuasion_strategy=default_persuasion_for_type(ptype),
        visual_style=default_visual_style_for_type(ptype),
        depth_level=depth_from_service_depths(service_depths),
        audience_mode=infer_audience_mode(request.audience, ptype),
        presentation_type=ptype,
    )


def presentation_intent_from_mission(
    mission: ProjectMission,
    *,
    presentation_type: PresentationType,
    audience: str,
    purpose: str,
    key_message: str,
) -> PresentationIntent:
    return PresentationIntent(
        audience=audience,
        purpose=purpose,
        key_message=key_message,
        persuasion_strategy=default_persuasion_for_type(presentation_type),
        visual_style=default_visual_style_for_type(presentation_type),
        depth_level=depth_from_service_depths(list(mission.requested_service_depths)),
        audience_mode=infer_audience_mode(audience, presentation_type),
        presentation_type=presentation_type,
    )


def ensure_brief_presentation_intent(brief: PresentationBrief) -> PresentationBrief:
    intent = presentation_intent_from_brief(brief)
    if brief.presentation_intent is not None and not brief.presentation_intent.is_empty():
        # Fill only missing persuasion / visual / depth
        merged = brief.presentation_intent.model_copy(
            update={
                "persuasion_strategy": (
                    brief.presentation_intent.persuasion_strategy.strip()
                    or intent.persuasion_strategy
                ),
                "visual_style": (
                    brief.presentation_intent.visual_style.strip() or intent.visual_style
                ),
                "depth_level": (
                    brief.presentation_intent.depth_level.strip() or intent.depth_level
                ),
                "audience_mode": brief.presentation_intent.audience_mode
                or intent.audience_mode,
                "audience": brief.presentation_intent.audience or brief.audience,
                "purpose": brief.presentation_intent.purpose or brief.purpose,
                "key_message": brief.presentation_intent.key_message or brief.core_message,
                "presentation_type": brief.presentation_type,
            }
        )
        return brief.model_copy(update={"presentation_intent": merged})
    return brief.model_copy(update={"presentation_intent": intent})


def ensure_slide_role_layer(
    slide: SlideSpec,
    *,
    narrative_stage: NarrativeStage | None = None,
) -> SlideSpec:
    role = resolve_slide_role(
        page_archetype=slide.page_archetype,
        narrative_stage=narrative_stage,
        slide_type=slide.slide_type,
        existing=slide.slide_role,
    )
    strategy = slide.visual_strategy
    if strategy is None or strategy.is_empty():
        strategy = visual_strategy_from_role(role, page_archetype=slide.page_archetype)
    return slide.model_copy(update={"slide_role": role, "visual_strategy": strategy})


def ensure_slide_intent_role_layer(intent: SlideIntent) -> SlideIntent:
    role = resolve_slide_role(
        page_archetype=intent.page_archetype,
        existing=intent.slide_role,
    )
    strategy = intent.visual_strategy
    if strategy is None or strategy.is_empty():
        strategy = visual_strategy_from_role(role, page_archetype=intent.page_archetype)
    return intent.model_copy(update={"slide_role": role, "visual_strategy": strategy})
