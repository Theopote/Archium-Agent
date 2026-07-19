"""Persist Presentation Studio human visual reviews to JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.visual.benchmark import HumanVisualReview


def _reviews_path(presentation_id: UUID, *, settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return resolved.output_path / "studio-reviews" / f"{presentation_id}.json"


def load_presentation_reviews(
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> dict[str, HumanVisualReview]:
    path = _reviews_path(presentation_id, settings=settings)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    reviews: dict[str, HumanVisualReview] = {}
    for slide_id, item in payload.items():
        if isinstance(item, dict):
            try:
                reviews[str(slide_id)] = HumanVisualReview.model_validate(item)
            except Exception:
                continue
    return reviews


def load_slide_review(
    presentation_id: UUID,
    slide_id: UUID,
    *,
    settings: Settings | None = None,
) -> HumanVisualReview | None:
    return load_presentation_reviews(presentation_id, settings=settings).get(str(slide_id))


def save_slide_review(
    presentation_id: UUID,
    slide_id: UUID,
    review: HumanVisualReview,
    *,
    settings: Settings | None = None,
) -> Path:
    path = _reviews_path(presentation_id, settings=settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = {
        str(key): value.model_dump(mode="json")
        for key, value in load_presentation_reviews(presentation_id, settings=settings).items()
    }
    store[str(slide_id)] = review.model_dump(mode="json")
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
