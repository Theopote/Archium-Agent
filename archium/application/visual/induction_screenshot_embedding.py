"""Attach screenshot fingerprints to parsed reference slides."""

from __future__ import annotations

from pathlib import Path

from archium.domain.visual.reference_slide import ReferenceSlideSnapshot
from archium.infrastructure.vision.screenshot_embedding import try_compute_screenshot_embedding


def enrich_slide_screenshot_embeddings(
    slides: list[ReferenceSlideSnapshot],
    workspace: Path,
    *,
    enabled: bool = True,
) -> tuple[list[ReferenceSlideSnapshot], int]:
    """Return slides with ``screenshot_embedding`` filled when PNGs are present."""
    if not enabled:
        return slides, 0
    enriched: list[ReferenceSlideSnapshot] = []
    attached = 0
    for slide in slides:
        if slide.screenshot_embedding:
            enriched.append(slide)
            attached += 1
            continue
        rel = (slide.image_path or "").strip()
        if not rel:
            enriched.append(slide)
            continue
        emb = try_compute_screenshot_embedding(workspace / rel)
        if emb is None:
            enriched.append(slide)
            continue
        enriched.append(slide.model_copy(update={"screenshot_embedding": emb}))
        attached += 1
    return enriched, attached
