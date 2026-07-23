"""Apply Visual Grammar evidence slots onto SlideSpec (VG-002)."""

from __future__ import annotations

from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.visual.visual_grammar import (
    EvidenceSlot,
    PageArchetype,
    VisualPageRecipe,
    get_recipe,
)

_GRAMMAR_TAG = "[grammar:"


def _slot_satisfied(slide: SlideSpec, slot: EvidenceSlot) -> bool:
    if slot.visual_types:
        for req in slide.visual_requirements:
            if req.type in slot.visual_types:
                return True
            if _GRAMMAR_TAG + slot.role in req.description:
                return True
    if slot.accepts_text:
        blob = " ".join([slide.message, *slide.key_points, slide.title])
        if slot.role.replace("_", "") in blob.casefold().replace("_", "").replace(" ", ""):
            return True
        # Text slots are satisfied when the slide carries substantive text points.
        if slide.key_points or len(slide.message.strip()) >= 8:
            return True
    return False


def ensure_evidence_slots_on_slide(
    slide: SlideSpec,
    *,
    archetype: PageArchetype | None = None,
    recipe: VisualPageRecipe | None = None,
) -> SlideSpec:
    """Stamp page_archetype and ensure required evidence slots exist as requirements."""
    resolved_archetype = archetype or slide.page_archetype
    if resolved_archetype is None or resolved_archetype == PageArchetype.GENERIC:
        return slide

    resolved = recipe or get_recipe(resolved_archetype)
    slots = resolved.required_evidence_slots
    if not slots:
        return slide.model_copy(
            update={
                "page_archetype": resolved_archetype,
                "required_evidence_slots": [],
            }
        )

    requirements = list(slide.visual_requirements)
    for slot in slots:
        if not slot.required or _slot_satisfied(slide, slot):
            continue
        if not slot.visual_types and slot.accepts_text:
            # Text-only slots are tracked on required_evidence_slots, not as visuals.
            continue
        visual_type = next(iter(slot.visual_types), VisualType.SITE_PHOTO)
        requirements.append(
            SlideVisualRequirement(
                type=visual_type,
                description=f"{_GRAMMAR_TAG}{slot.role}] {slot.description}",
                required=True,
            )
        )

    return slide.model_copy(
        update={
            "page_archetype": resolved_archetype,
            "required_evidence_slots": [slot.role for slot in slots if slot.required],
            "visual_requirements": requirements,
        }
    )


def missing_evidence_slots(slide: SlideSpec) -> list[EvidenceSlot]:
    """Return required slots that are still unsatisfied on the slide."""
    if slide.page_archetype is None or slide.page_archetype == PageArchetype.GENERIC:
        return []
    recipe = get_recipe(slide.page_archetype)
    return [
        slot
        for slot in recipe.required_evidence_slots
        if slot.required and not _slot_satisfied(slide, slot)
    ]
