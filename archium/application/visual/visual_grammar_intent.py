"""Apply Visual Grammar recipes to VisualIntent drafts and layout preferences."""

from __future__ import annotations

from archium.application.visual.layout_style_preference import LayoutStylePreference
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.visual_grammar import PageArchetype, VisualPageRecipe, get_recipe
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.visual_schemas import VisualIntentDraft


def _implemented_families() -> set[LayoutFamily]:
    return {item.family for item in get_layout_family_registry().implemented()}


def _filter_families(families: tuple[LayoutFamily, ...]) -> list[LayoutFamily]:
    implemented = _implemented_families()
    filtered = [family for family in families if family in implemented]
    return filtered or [LayoutFamily.TEXTUAL_ARGUMENT]


def apply_grammar_to_draft(
    draft: VisualIntentDraft,
    recipe: VisualPageRecipe,
) -> VisualIntentDraft:
    """Merge grammar recipe onto a VisualIntentDraft (rule or LLM origin)."""
    preferred = _filter_families(recipe.preferred_layout_families)
    forbidden = recipe.forbidden_layout_families
    merged_families = [f for f in preferred if f not in forbidden]
    if not merged_families:
        merged_families = _filter_families(recipe.preferred_layout_families)

    # Preserve LLM families that are not forbidden, ranked after grammar.
    for family in draft.preferred_layout_families:
        if family in forbidden or family in merged_families:
            continue
        if family in _implemented_families():
            merged_families.append(family)
    merged_families = merged_families[:3]

    return draft.model_copy(
        update={
            "dominant_content_type": recipe.dominant_content_type,
            "preferred_layout_families": merged_families,
            "hierarchy": list(recipe.reading_order),
            "reading_order": list(recipe.reading_order),
            "composition_strategy": recipe.composition_strategy,
            "image_treatment": recipe.image_treatment,
            "annotation_strategy": recipe.annotation_strategy,
            "density_level": recipe.default_density,
            "emotional_tone": recipe.emotional_tone,
            "continuity_role": recipe.continuity_role,
        }
    )


def apply_grammar_to_intent(
    intent: VisualIntent,
    *,
    page_archetype: PageArchetype,
    recipe: VisualPageRecipe | None = None,
) -> VisualIntent:
    """Set page_archetype and align intent fields with the grammar recipe."""
    resolved = recipe or get_recipe(page_archetype)
    if page_archetype == PageArchetype.GENERIC:
        return intent.model_copy(update={"page_archetype": page_archetype})

    preferred = _filter_families(resolved.preferred_layout_families)
    forbidden = resolved.forbidden_layout_families
    merged = [f for f in preferred if f not in forbidden]
    for family in intent.preferred_layout_families:
        if family not in forbidden and family not in merged:
            merged.append(family)
    merged = merged[:3]

    return intent.model_copy(
        update={
            "page_archetype": page_archetype,
            "dominant_content_type": resolved.dominant_content_type,
            "preferred_layout_families": merged,
            "hierarchy": list(resolved.reading_order),
            "reading_order": list(resolved.reading_order),
            "composition_strategy": resolved.composition_strategy,
            "image_treatment": resolved.image_treatment,
            "annotation_strategy": resolved.annotation_strategy,
            "density_level": resolved.default_density,
            "emotional_tone": resolved.emotional_tone,
            "continuity_role": resolved.continuity_role,
        }
    )


def preferred_variant_for_intent(
    intent: VisualIntent,
    family: LayoutFamily,
) -> str | None:
    """Grammar-preferred variant for a layout family, if any."""
    if intent.page_archetype is None or intent.page_archetype == PageArchetype.GENERIC:
        return None
    recipe = get_recipe(intent.page_archetype)
    for pref_family, variant in recipe.preferred_variants:
        if pref_family == family:
            return variant
    return None


def order_variants_for_intent(
    intent: VisualIntent,
    family: LayoutFamily,
    variants: tuple[str, ...] | list[str],
) -> list[str]:
    """Rank variants with grammar archetype preference first."""
    ordered = list(variants)
    grammar_variant = preferred_variant_for_intent(intent, family)
    if grammar_variant and grammar_variant in ordered:
        return [grammar_variant, *[v for v in ordered if v != grammar_variant]]
    return ordered


def forbidden_families_for_intent(intent: VisualIntent) -> frozenset[LayoutFamily]:
    """Layout families blocked by the slide's visual grammar archetype."""
    if intent.page_archetype is None or intent.page_archetype == PageArchetype.GENERIC:
        return frozenset()
    return get_recipe(intent.page_archetype).forbidden_layout_families


def derive_grammar_layout_preference(intent: VisualIntent) -> LayoutStylePreference:
    """Layout family/variant ranking from recognized page archetype."""
    if intent.page_archetype is None or intent.page_archetype == PageArchetype.GENERIC:
        return LayoutStylePreference()

    recipe = get_recipe(intent.page_archetype)
    implemented = _implemented_families()
    families = tuple(
        family for family in recipe.preferred_layout_families if family in implemented
    )
    variants = tuple(
        (family, variant)
        for family, variant in recipe.preferred_variants
        if family in implemented
    )
    notes: tuple[str, ...] = (f"visual_grammar:{intent.page_archetype.value}",)
    if intent.composition_strategy:
        notes = (*notes, f"visual_grammar:strategy:{intent.composition_strategy[:80]}")
    return LayoutStylePreference(
        preferred_families=families,
        preferred_variants=variants,
        notes=notes,
    )


def merge_layout_style_preferences(
    *preferences: LayoutStylePreference,
) -> LayoutStylePreference:
    """Merge style preferences; earlier groups win rank."""
    families: list[LayoutFamily] = []
    variants: list[tuple[LayoutFamily, str]] = []
    notes: list[str] = []
    seen_families: set[LayoutFamily] = set()
    seen_variants: set[tuple[LayoutFamily, str]] = set()

    for pref in preferences:
        if pref.is_empty:
            continue
        for family in pref.preferred_families:
            if family in seen_families:
                continue
            seen_families.add(family)
            families.append(family)
        for key in pref.preferred_variants:
            if key in seen_variants:
                continue
            seen_variants.add(key)
            variants.append(key)
        notes.extend(pref.notes)

    return LayoutStylePreference(
        preferred_families=tuple(families),
        preferred_variants=tuple(variants),
        notes=tuple(notes),
    )
