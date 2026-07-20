"""Build human-review fields for benchmark summary rows."""

from __future__ import annotations

from typing import Any

from archium.domain.visual.benchmark import HUMAN_REVIEW_PENDING_LABEL, HumanVisualReview


def human_review_summary_fields(review: HumanVisualReview | None) -> dict[str, Any]:
    if review is None:
        return {
            "human_weighted_score": None,
            "human_score_label": HUMAN_REVIEW_PENDING_LABEL,
            "human_review_source": None,
            "human_accepted_for_delivery": False,
            "human_accepted": None,
            "reviewer": None,
            "reviewed_at": None,
            "major_problems": [],
        }

    manual = review.is_manual_review()
    invalidated = review.is_invalidated()
    return {
        "human_weighted_score": review.reportable_weighted_score(),
        "human_score_label": review.human_score_label(),
        "human_review_source": review.source.value,
        "human_review_validity": review.validity.value,
        "human_review_completed": bool(review.review_completed or manual),
        "human_accepted_for_delivery": bool(manual and review.accepted_for_delivery),
        "human_accepted": review.accepted_for_delivery if manual else None,
        "human_invalidated": invalidated,
        "invalidation_reason": review.invalidation_reason if invalidated else None,
        "reviewer": review.reviewer or None,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "major_problems": review.major_problems if manual else [],
    }
