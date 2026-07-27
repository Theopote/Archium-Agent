"""Deck-level illustrative style lock (Topic 06 Phase P2 / APP-025).

Shares VisionStylePreset (+ light DNA) across non-evidence pages from the
selected ConceptDirection / canonical VisualConceptBrief. Does not change
ArtDirection (layout chrome) or invent a new Agent.
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.application.visual.vision.concept_direction_visual_seed import (
    build_direction_seed_elements,
    resolve_style_from_visual_prompt,
)
from archium.application.visual.vision.visual_concept_brief_intent import (
    visual_concept_brief_applies,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.visual.vision_generation import ImageRequest, VisionStylePreset
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual.visual_grammar import PageArchetype


@dataclass(frozen=True)
class DeckIllustrativeStyleLock:
    """Shared illustrative style DNA for one design direction / deck."""

    style: VisionStylePreset | str
    dna_elements: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    source: str = ""  # concept_direction | brief | massing_slot

    def style_value(self) -> str:
        if isinstance(self.style, VisionStylePreset):
            return self.style.value
        return str(self.style)


def resolve_deck_illustrative_style_lock(
    *,
    direction: ConceptDirection | None = None,
    brief: VisualConceptBrief | None = None,
) -> DeckIllustrativeStyleLock | None:
    """Resolve lock from direction visual_prompt, else canonical brief style."""
    if direction is not None and direction.visual_prompt is not None:
        vp = direction.visual_prompt
        if vp.style.strip() or vp.image_prompt.strip():
            style = resolve_style_from_visual_prompt(vp.style)
            dna = tuple(build_direction_seed_elements(direction)[:6])
            avoid: tuple[str, ...] = (
                "luxury commercial real-estate rendering",
                "photorealistic site survey photo presented as evidence",
            )
            return DeckIllustrativeStyleLock(
                style=style,
                dna_elements=dna,
                avoid=avoid,
                source="concept_direction",
            )

    if brief is not None and _brief_style_raw(brief):
        style = resolve_style_from_visual_prompt(str(_brief_style_raw(brief)))
        dna = tuple(str(e).strip() for e in (brief.elements or []) if str(e).strip())[:6]
        avoid = tuple(str(a).strip() for a in (brief.avoid or []) if str(a).strip())[:6]
        slot = str((brief.extra_json or {}).get("slot_key") or "")
        source = "massing_slot" if slot == "massing" else ("brief_slot" if slot else "brief")
        return DeckIllustrativeStyleLock(
            style=style,
            dna_elements=dna,
            avoid=avoid
            or (
                "luxury commercial real-estate rendering",
                "photorealistic site survey photo presented as evidence",
            ),
            source=source,
        )
    return None


def apply_deck_illustrative_style_lock(
    request: ImageRequest,
    lock: DeckIllustrativeStyleLock | None,
    *,
    page_archetype: PageArchetype | str | None = None,
) -> ImageRequest:
    """Overwrite request.style (+ merge DNA); keep image_type / subject / purpose."""
    if lock is None:
        return request
    if not visual_concept_brief_applies(page_archetype=page_archetype):
        return request

    elements = list(request.elements)
    for item in lock.dna_elements:
        if item and item not in elements:
            elements.append(item)
    avoid = list(request.avoid)
    for item in lock.avoid:
        if item and item not in avoid:
            avoid.append(item)

    seed = (request.seed_source or "").strip()
    if seed and "deck_lock" not in seed:
        seed = f"{seed}+deck_lock"
    elif not seed:
        seed = f"deck_lock:{lock.source}"

    return request.model_copy(
        update={
            "style": lock.style,
            "elements": elements[:12],
            "avoid": avoid[:12],
            "seed_source": seed[:40],
            "asset_policy": request.asset_policy,  # keep illustrative
        }
    )


def pick_canonical_visual_concept_brief(
    briefs: list[VisualConceptBrief],
) -> VisualConceptBrief | None:
    """Prefer non-slot briefs, then massing slot, then newest."""
    if not briefs:
        return None
    non_slot = [
        b for b in briefs if not str((b.extra_json or {}).get("slot_key") or "").strip()
    ]
    if non_slot:
        return non_slot[0]
    massing = [
        b
        for b in briefs
        if str((b.extra_json or {}).get("slot_key") or "") == "massing"
    ]
    if massing:
        return massing[0]
    return briefs[0]


def _brief_style_raw(brief: VisualConceptBrief) -> str:
    preset = brief.style_preset
    if isinstance(preset, VisionStylePreset):
        return preset.value
    return str(preset or "").strip()
