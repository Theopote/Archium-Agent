"""Lineage helpers for Brief and Storyline regeneration."""

from __future__ import annotations

from archium.domain.cultural_narrative import CULTURAL_NARRATIVE_LOGICAL_KEY, CulturalNarrativePlan
from archium.domain.outline import OUTLINE_LOGICAL_KEY, OutlinePlan
from archium.domain.presentation import (
    BRIEF_LOGICAL_KEY,
    STORYLINE_LOGICAL_KEY,
    PresentationBrief,
    Storyline,
)


def apply_brief_lineage(
    brief: PresentationBrief,
    previous: PresentationBrief | None,
) -> PresentationBrief:
    brief.logical_key = BRIEF_LOGICAL_KEY
    if previous is None:
        return brief
    brief.lineage_id = previous.lineage_id
    brief.version = previous.version + 1
    return brief


def apply_storyline_lineage(
    storyline: Storyline,
    previous: Storyline | None,
) -> Storyline:
    storyline.logical_key = STORYLINE_LOGICAL_KEY
    if previous is None:
        return storyline
    storyline.lineage_id = previous.lineage_id
    storyline.version = previous.version + 1
    return storyline


def apply_outline_lineage(
    outline: OutlinePlan,
    previous: OutlinePlan | None,
) -> OutlinePlan:
    outline.logical_key = OUTLINE_LOGICAL_KEY
    if previous is None:
        return outline
    outline.lineage_id = previous.lineage_id
    outline.version = previous.version + 1
    return outline


def apply_cultural_narrative_lineage(
    plan: CulturalNarrativePlan,
    previous: CulturalNarrativePlan | None,
) -> CulturalNarrativePlan:
    plan.logical_key = CULTURAL_NARRATIVE_LOGICAL_KEY
    if previous is None:
        return plan
    plan.lineage_id = previous.lineage_id
    plan.version = previous.version + 1
    return plan
