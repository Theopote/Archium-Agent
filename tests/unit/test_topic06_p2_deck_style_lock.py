"""Topic 06 P2 — deck illustrative style lock (APP-025)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision.concept_direction_visual_seed import (
    image_request_from_concept_direction,
)
from archium.application.visual.vision.deck_illustrative_style_lock import (
    apply_deck_illustrative_style_lock,
    pick_canonical_visual_concept_brief,
    resolve_deck_illustrative_style_lock,
)
from archium.application.visual.vision.intent_suggester import suggest_image_request_for_slide
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.vision_generation import VisionStylePreset
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual.visual_grammar import PageArchetype


def _direction_with_marker_style() -> ConceptDirection:
    return ConceptDirection(
        project_id=uuid4(),
        title="庭院核",
        summary="内向院落",
        visual_prompt=ConceptVisualPrompt(
            image_prompt="courtyard cultural core",
            camera="axonometric",
            style="marker sketch",
        ),
        spatial_strategy="四面围合",
        formal_language="体量咬合",
    )


def test_resolve_lock_from_direction_style() -> None:
    lock = resolve_deck_illustrative_style_lock(direction=_direction_with_marker_style())
    assert lock is not None
    assert lock.source == "concept_direction"
    assert lock.style_value() == VisionStylePreset.MARKER_SKETCH.value


def test_apply_lock_unifies_suggester_style_keeps_image_type() -> None:
    direction = _direction_with_marker_style()
    lock = resolve_deck_illustrative_style_lock(direction=direction)
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="设计策略",
        message="流线示意",
        slide_type=SlideType.CONTENT,
    )
    suggested = suggest_image_request_for_slide(
        slide, page_archetype=PageArchetype.DESIGN_STRATEGY
    )
    assert suggested is not None
    original_type = suggested.image_type
    locked = apply_deck_illustrative_style_lock(
        suggested, lock, page_archetype=PageArchetype.DESIGN_STRATEGY
    )
    assert locked.image_type == original_type
    assert locked.style == VisionStylePreset.MARKER_SKETCH
    assert "deck_lock" in locked.seed_source


def test_evidence_archetype_skips_lock() -> None:
    direction = _direction_with_marker_style()
    lock = resolve_deck_illustrative_style_lock(direction=direction)
    request = image_request_from_concept_direction(direction)
    locked = apply_deck_illustrative_style_lock(
        request, lock, page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS
    )
    assert locked is request


def test_pick_canonical_brief_prefers_non_slot() -> None:
    pid = uuid4()
    did = uuid4()
    slot = VisualConceptBrief(
        project_id=pid,
        concept_direction_id=did,
        title="氛围槽",
        style_preset=VisionStylePreset.SOFT_ATMOSPHERE,
        extra_json={"slot_key": "atmosphere"},
    )
    canonical = VisualConceptBrief(
        project_id=pid,
        concept_direction_id=did,
        title="主简报",
        style_preset=VisionStylePreset.MARKER_SKETCH,
        extra_json={},
    )
    # Newest-first list as repository returns
    picked = pick_canonical_visual_concept_brief([slot, canonical])
    assert picked is not None
    assert picked.title == "主简报"


def test_slot_style_yields_to_direction_lock() -> None:
    """Simulate VT slot: would pass soft_atmosphere, lock forces marker from direction."""
    direction = _direction_with_marker_style()
    lock = resolve_deck_illustrative_style_lock(direction=direction)
    assert lock is not None
    # Slot would have suggested soft atmosphere; lock overwrites
    from archium.domain.visual.vision_generation import ArchitectureImageType, ImageRequest

    slot_request = ImageRequest(
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        subject="atmosphere",
        style=VisionStylePreset.SOFT_ATMOSPHERE,
        seed_source="brief",
    )
    locked = apply_deck_illustrative_style_lock(
        slot_request, lock, page_archetype=PageArchetype.NARRATIVE_OPENING
    )
    assert locked.image_type == ArchitectureImageType.ATMOSPHERE_IMAGE
    assert locked.style == VisionStylePreset.MARKER_SKETCH
