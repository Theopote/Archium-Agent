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
            "page_quality_status": None,
            "reporting_ready": None,
            "selected_issue_codes": [],
            "scoring_mode": None,
        }

    manual = review.is_manual_review()
    invalidated = review.is_invalidated()
    status = None
    if manual and not invalidated and not review.is_scaffold_review():
        status = review.derived_page_quality_status().value
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
        "page_quality_status": status,
        "reporting_ready": review.reporting_ready.value if manual else None,
        "selected_issue_codes": list(review.selected_issue_codes) if manual else [],
        "scoring_mode": review.scoring_mode.value if manual else None,
    }
