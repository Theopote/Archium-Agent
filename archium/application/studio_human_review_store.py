"""Persist Presentation Studio human visual reviews to DB and JSON."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.human_visual_review_service import HumanVisualReviewService
from archium.config.settings import Settings, get_settings
from archium.domain.visual.benchmark import HumanVisualReview


def _reviews_path(presentation_id: UUID, *, settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return resolved.output_path / "studio-reviews" / f"{presentation_id}.json"


def _load_json_reviews(
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


def _write_json_reviews(
    presentation_id: UUID,
    store: dict[str, HumanVisualReview],
    *,
    settings: Settings | None = None,
) -> Path:
    path = _reviews_path(presentation_id, settings=settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: value.model_dump(mode="json")
        for key, value in store.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_presentation_reviews(
    session: Session | None,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> dict[str, HumanVisualReview]:
    if session is not None:
        db_reviews = HumanVisualReviewService(session).load_for_presentation(presentation_id)
        if db_reviews:
            return {review.case_id: review for review in db_reviews}
    return _load_json_reviews(presentation_id, settings=settings)


def load_slide_review(
    session: Session | None,
    presentation_id: UUID,
    slide_id: UUID,
    *,
    settings: Settings | None = None,
) -> HumanVisualReview | None:
    if session is not None:
        review = HumanVisualReviewService(session).load_for_slide(presentation_id, slide_id)
        if review is not None:
            return review
    return _load_json_reviews(presentation_id, settings=settings).get(str(slide_id))


def save_slide_review(
    session: Session,
    presentation_id: UUID,
    slide_id: UUID,
    review: HumanVisualReview,
    *,
    settings: Settings | None = None,
) -> Path:
    HumanVisualReviewService(session).save(
        presentation_id=presentation_id,
        slide_id=slide_id,
        review=review,
    )
    store = _load_json_reviews(presentation_id, settings=settings)
    store[str(slide_id)] = review
    return _write_json_reviews(presentation_id, store, settings=settings)
