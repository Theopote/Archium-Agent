"""Recognize architectural page archetypes from SlideSpec signals (VG-002)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec
from archium.domain.visual.visual_grammar import (
    PageArchetype,
    VisualPageRecipe,
    get_visual_grammar_registry,
)

# Minimum score to accept a non-GENERIC archetype (tuned for rule-based V1).
_RECOGNITION_THRESHOLD = 2.0


@dataclass(frozen=True)
class ArchetypeRecognition:
    """Result of page-archetype recognition."""

    archetype: PageArchetype
    confidence: float
    evidence: tuple[str, ...]
    recipe: VisualPageRecipe


def _slide_blob(slide: SlideSpec) -> str:
    parts = [
        slide.title,
        slide.message,
        *slide.key_points,
        *(req.description for req in slide.visual_requirements),
    ]
    return " ".join(parts).casefold()


def _primary_visual_types(slide: SlideSpec) -> set[VisualType]:
    types: set[VisualType] = set()
    for req in slide.visual_requirements:
        if req.type != VisualType.TEXT_ONLY:
            types.add(req.type)
    return types


def _score_recipe(
    recipe: VisualPageRecipe,
    *,
    blob: str,
    slide: SlideSpec,
    visual_types: set[VisualType],
) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []

    for signal in recipe.title_signals:
        if signal.pattern.search(slide.title):
            score += signal.weight * 1.2
            evidence.append(f"title:{signal.label or signal.pattern.pattern}")

    for signal in recipe.body_signals:
        if signal.pattern.search(blob):
            score += signal.weight
            evidence.append(f"body:{signal.label or signal.pattern.pattern}")

    if recipe.visual_type_hints and visual_types:
        overlap = visual_types & recipe.visual_type_hints
        if overlap:
            score += 1.5 * len(overlap)
            evidence.append(
                "visual:" + ",".join(sorted(item.value for item in overlap))
            )

    if recipe.slide_type_hints and slide.slide_type in recipe.slide_type_hints:
        score += 1.5
        evidence.append(f"slide_type:{slide.slide_type.value}")

    # Page-order is only a tie-breaker / boost when other signals already fired.
    if (
        recipe.preferred_page_orders
        and slide.order in recipe.preferred_page_orders
        and score >= 1.0
    ):
        score += 1.8
        evidence.append(f"page_order:{slide.order}")

    return score, evidence


def recognize_page_archetype(slide: SlideSpec) -> ArchetypeRecognition:
    """Score all recipes and return the best-matching archetype."""
    if slide.page_archetype is not None and slide.page_archetype != PageArchetype.GENERIC:
        recipe = get_visual_grammar_registry()[slide.page_archetype]
        return ArchetypeRecognition(
            archetype=slide.page_archetype,
            confidence=10.0,
            evidence=("slide.page_archetype",),
            recipe=recipe,
        )

    registry = get_visual_grammar_registry()
    blob = _slide_blob(slide)
    visual_types = _primary_visual_types(slide)

    best_archetype = PageArchetype.GENERIC
    best_score = 0.0
    best_evidence: list[str] = []

    for archetype, recipe in registry.items():
        if archetype == PageArchetype.GENERIC:
            continue
        score, evidence = _score_recipe(
            recipe,
            blob=blob,
            slide=slide,
            visual_types=visual_types,
        )
        if score > best_score:
            best_score = score
            best_archetype = archetype
            best_evidence = evidence

    if best_score < _RECOGNITION_THRESHOLD:
        generic = registry[PageArchetype.GENERIC]
        return ArchetypeRecognition(
            archetype=PageArchetype.GENERIC,
            confidence=0.0,
            evidence=(),
            recipe=generic,
        )

    return ArchetypeRecognition(
        archetype=best_archetype,
        confidence=best_score,
        evidence=tuple(best_evidence),
        recipe=registry[best_archetype],
    )
