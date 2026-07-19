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
    return {
        "human_weighted_score": review.reportable_weighted_score(),
        "human_score_label": review.human_score_label(),
        "human_review_source": review.source.value,
        "human_accepted_for_delivery": bool(manual and review.accepted),
        "human_accepted": review.accepted if manual else None,
        "reviewer": review.reviewer or None,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "major_problems": review.major_problems if manual else [],
    }
