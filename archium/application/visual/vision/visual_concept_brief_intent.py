"""Map VisualConceptBrief onto VisualIntent / ImageRequest (Vision Engine)."""

from __future__ import annotations

from archium.domain.visual.vision_generation import (
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationMode,
)
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent

# Concept / narrative pages may inherit the selected direction's visual DNA.
# Evidence-led diagnosis pages must not auto-bind illustrative concept art.
_CONCEPT_FRIENDLY_ARCHETYPES = frozenset(
    {
        PageArchetype.NARRATIVE_OPENING,
        PageArchetype.DESIGN_STRATEGY,
        PageArchetype.BEFORE_AFTER_TRANSFORMATION,
        PageArchetype.GENERIC,
    }
)


def visual_concept_brief_applies(*, page_archetype: PageArchetype | str | None) -> bool:
    """Whether a VisualConceptBrief may seed this page's illustrative ImageRequest."""
    if page_archetype is None:
        return True
    if isinstance(page_archetype, str):
        try:
            page_archetype = PageArchetype(page_archetype)
        except ValueError:
            return True
    if page_archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS:
        return False
    return page_archetype in _CONCEPT_FRIENDLY_ARCHETYPES


def image_request_from_visual_concept_brief(brief: VisualConceptBrief) -> ImageRequest:
    """Build an illustrative ImageRequest from a persisted visual concept brief."""
    purpose_parts = [
        brief.composition_intent,
        brief.atmosphere,
        brief.diagram_intent,
    ]
    purpose = " ".join(part for part in purpose_parts if part).strip()[:500]
    return ImageRequest(
        image_type=brief.image_type,
        subject=brief.subject or brief.title,
        purpose=purpose or "concept visual exploration",
        style=brief.style_preset,
        elements=list(brief.elements),
        avoid=list(brief.avoid),
        asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
        mode=VisionGenerationMode.TEXT_TO_IMAGE,
    )


def apply_visual_concept_brief_to_intent(
    intent: VisualIntent,
    brief: VisualConceptBrief,
) -> VisualIntent:
    """Seed ImageRequest / optional hero asset from a concept visual brief.

    Never overrides an existing image_request or grammar/design-brief hero asset.
    """
    updates: dict[str, object] = {}
    if intent.image_request is None:
        updates["image_request"] = image_request_from_visual_concept_brief(brief)
    if intent.hero_asset_id is None and brief.asset_id is not None:
        updates["hero_asset_id"] = brief.asset_id
    if not (intent.emotional_tone or "").strip() and brief.atmosphere.strip():
        updates["emotional_tone"] = brief.atmosphere.strip()[:200]
    if not (intent.composition_strategy or "").strip() and brief.composition_intent.strip():
        updates["composition_strategy"] = brief.composition_intent.strip()[:500]
    if not updates:
        return intent
    return intent.model_copy(update=updates)
