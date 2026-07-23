"""Recognize architectural page archetypes from content signals (VG-002)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec
from archium.domain.slide_intent import SlideIntent
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


def _score_recipe(
    recipe: VisualPageRecipe,
    *,
    title: str,
    blob: str,
    order: int,
    slide_type: SlideType | None,
    visual_types: set[VisualType],
) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []

    for signal in recipe.title_signals:
        if signal.pattern.search(title):
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

    if (
        slide_type is not None
        and recipe.slide_type_hints
        and slide_type in recipe.slide_type_hints
    ):
        score += 1.5
        evidence.append(f"slide_type:{slide_type.value}")

    # Page-order is only a boost when other signals already fired.
    if recipe.preferred_page_orders and order in recipe.preferred_page_orders and score >= 1.0:
        score += 1.8
        evidence.append(f"page_order:{order}")

    return score, evidence


def recognize_page_archetype_from_signals(
    *,
    title: str,
    body: str = "",
    order: int = 0,
    slide_type: SlideType | None = None,
    visual_types: set[VisualType] | None = None,
    explicit: PageArchetype | None = None,
) -> ArchetypeRecognition:
    """Score recipes from free-form title/body signals (Outline / Brief / Slide)."""
    registry = get_visual_grammar_registry()
    if explicit is not None and explicit != PageArchetype.GENERIC:
        return ArchetypeRecognition(
            archetype=explicit,
            confidence=10.0,
            evidence=("explicit_page_archetype",),
            recipe=registry[explicit],
        )

    blob = f"{title} {body}".casefold()
    types = visual_types or set()
    best_archetype = PageArchetype.GENERIC
    best_score = 0.0
    best_evidence: list[str] = []

    for archetype, recipe in registry.items():
        if archetype == PageArchetype.GENERIC:
            continue
        score, evidence = _score_recipe(
            recipe,
            title=title,
            blob=blob,
            order=order,
            slide_type=slide_type,
            visual_types=types,
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


def recognize_page_archetype_from_intent(intent: SlideIntent) -> ArchetypeRecognition:
    """Recognize archetype from a SlideIntent card (pre-SlideSpec)."""
    body = " ".join(
        [
            intent.central_conclusion,
            *intent.required_evidence,
            *intent.required_assets,
            intent.notes,
            intent.expected_layout,
        ]
    )
    return recognize_page_archetype_from_signals(
        title=intent.page_task,
        body=body,
        order=intent.order,
        explicit=intent.page_archetype,
    )


def recognize_page_archetype(slide: SlideSpec) -> ArchetypeRecognition:
    """Score all recipes and return the best-matching archetype for a SlideSpec."""
    visual_types: set[VisualType] = set()
    for req in slide.visual_requirements:
        if req.type != VisualType.TEXT_ONLY:
            visual_types.add(req.type)
    body = " ".join(
        [
            slide.message,
            *slide.key_points,
            *(req.description for req in slide.visual_requirements),
        ]
    )
    return recognize_page_archetype_from_signals(
        title=slide.title,
        body=body,
        order=slide.order,
        slide_type=slide.slide_type,
        visual_types=visual_types,
        explicit=slide.page_archetype,
    )
