"""Lineage helpers for SlideSpec regeneration."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.domain.slide import SlideSpec, build_slide_logical_key


def apply_slide_lineage(
    new_slides: list[SlideSpec],
    previous_slides: list[SlideSpec],
) -> list[SlideSpec]:
    """Carry stable lineage IDs across slide regeneration when logical keys match."""
    lineage_by_key = {slide.logical_key: slide.lineage_id for slide in previous_slides}
    version_by_lineage = {slide.lineage_id: slide.version for slide in previous_slides}

    for slide in new_slides:
        slide.logical_key = build_slide_logical_key(slide.chapter_id, slide.order)
        existing_lineage = lineage_by_key.get(slide.logical_key)
        if existing_lineage is not None:
            slide.lineage_id = existing_lineage
            slide.version = version_by_lineage.get(existing_lineage, 1) + 1
        else:
            slide.lineage_id = uuid4()
            slide.version = 1
    return new_slides


def lineage_ids_from_revisions(revisions: list[object]) -> set[UUID]:
    lineage_ids: set[UUID] = set()
    for revision in revisions:
        lineage_id = getattr(revision, "lineage_id", None)
        if isinstance(lineage_id, UUID):
            lineage_ids.add(lineage_id)
    return lineage_ids
