"""Suggest illustrative ImageRequest from page archetype (Vision Engine v0.3).

Evidence-led archetypes intentionally return None - never auto-fill SITE_PHOTO slots.
"""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationMode,
    VisionStylePreset,
)
from archium.domain.visual.visual_grammar import PageArchetype


def suggest_image_request_for_slide(
    slide: SlideSpec,
    *,
    page_archetype: PageArchetype | None = None,
) -> ImageRequest | None:
    """Return an illustrative ImageRequest hint, or None when generation is inappropriate."""
    archetype = page_archetype or getattr(slide, "page_archetype", None) or PageArchetype.GENERIC
    if isinstance(archetype, str):
        try:
            archetype = PageArchetype(archetype)
        except ValueError:
            archetype = PageArchetype.GENERIC

    # Diagnosis pages are evidence-first; do not auto-suggest AI fill.
    if archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS:
        return None

    subject = (slide.message or slide.title or "").strip()
    if not subject:
        subject = "architectural presentation illustration"
    purpose = (slide.message or "").strip()
    elements = [slide.title] if slide.title else []

    if archetype == PageArchetype.NARRATIVE_OPENING:
        return ImageRequest(
            image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
            subject=subject,
            purpose=purpose or "narrative opening atmosphere",
            style=VisionStylePreset.SOFT_ATMOSPHERE,
            elements=elements,
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
        )
    if archetype == PageArchetype.SITE_CONTEXT_ANALYSIS:
        return ImageRequest(
            image_type=ArchitectureImageType.SITE_DIAGRAM,
            subject=subject,
            purpose=purpose or "site context diagram",
            style=VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
            elements=elements or ["site boundary", "access points"],
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
        )
    if archetype == PageArchetype.DESIGN_STRATEGY:
        return ImageRequest(
            image_type=ArchitectureImageType.FLOW_DIAGRAM,
            subject=subject,
            purpose=purpose or "design strategy diagram",
            style=VisionStylePreset.AXONOMETRIC_DIAGRAM,
            elements=elements or ["primary path", "strategy highlight"],
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
        )
    if archetype == PageArchetype.BEFORE_AFTER_TRANSFORMATION:
        return ImageRequest(
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            subject=subject,
            purpose=purpose or "before-after transformation concept",
            style=VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
            elements=elements or ["before cue", "after cue"],
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
        )
    # GENERIC / unknown: only suggest when the slide already leans diagrammatic.
    title_blob = f"{slide.title or ''} {slide.message or ''}".lower()
    if any(token in title_blob for token in ("策略", "流线", "示意", "concept", "diagram", "strategy")):
        return ImageRequest(
            image_type=ArchitectureImageType.PRESENTATION_ILLUSTRATION,
            subject=subject,
            purpose=purpose or "slide illustration",
            style=VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
            elements=elements,
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
        )
    return None
