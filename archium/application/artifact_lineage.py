"""Lineage helpers for Brief and Storyline regeneration."""

from __future__ import annotations

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
