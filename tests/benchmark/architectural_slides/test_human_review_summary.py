"""Tests for benchmark human review summary fields."""

from __future__ import annotations

from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_PENDING_LABEL,
    HumanVisualReview,
    HumanVisualReviewSource,
)

from tests.benchmark.architectural_slides.human_review_summary import human_review_summary_fields


def test_placeholder_review_summary_shows_pending_label() -> None:
    review = HumanVisualReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.PLACEHOLDER,
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
    )
    fields = human_review_summary_fields(review)
    assert fields["human_weighted_score"] is None
    assert fields["human_score_label"] == HUMAN_REVIEW_PENDING_LABEL
    assert fields["human_accepted_for_delivery"] is False


def test_manual_review_summary_includes_score_and_reviewer() -> None:
    from datetime import UTC, datetime

    review = HumanVisualReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=5,
        visual_focus=5,
        reading_order=5,
        image_text_relationship=5,
        whitespace_density=5,
        architectural_expression=5,
        aesthetic_finish=5,
        editability=5,
        reviewer="张工",
        reviewed_at=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        accepted=True,
    )
    fields = human_review_summary_fields(review)
    assert fields["human_weighted_score"] == 5.0
    assert fields["human_score_label"] == "5.00"
    assert fields["reviewer"] == "张工"
    assert fields["human_accepted_for_delivery"] is True
