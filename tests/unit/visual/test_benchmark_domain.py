"""Unit tests for architectural benchmark domain models."""

from __future__ import annotations

import pytest
from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_PASS_THRESHOLD,
    HumanVisualReview,
)


def test_human_visual_review_weighted_score() -> None:
    review = HumanVisualReview(
        case_id="case_001_site_plan",
        information_hierarchy=5,
        visual_focus=5,
        reading_order=5,
        image_text_relationship=5,
        whitespace_density=5,
        architectural_expression=5,
        aesthetic_finish=5,
        editability=5,
    )
    assert review.weighted_score() == 5.0
    assert review.passes_threshold()


def test_human_visual_review_threshold() -> None:
    review = HumanVisualReview(
        case_id="case_demo",
        information_hierarchy=3,
        visual_focus=3,
        reading_order=3,
        image_text_relationship=3,
        whitespace_density=3,
        architectural_expression=3,
        aesthetic_finish=3,
        editability=3,
    )
    assert review.weighted_score() == 3.0
    assert not review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD)


def test_human_visual_review_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        HumanVisualReview(
            case_id="case_demo",
            information_hierarchy=6,
            visual_focus=3,
            reading_order=3,
            image_text_relationship=3,
            whitespace_density=3,
            architectural_expression=3,
            aesthetic_finish=3,
            editability=3,
        )


def test_human_visual_review_infers_derived_source_from_notes() -> None:
    review = HumanVisualReview.model_validate(
        {
            "case_id": "case_demo",
            "information_hierarchy": 5,
            "visual_focus": 5,
            "reading_order": 5,
            "image_text_relationship": 5,
            "whitespace_density": 5,
            "architectural_expression": 5,
            "aesthetic_finish": 4,
            "editability": 5,
            "reviewer_notes": "Derived from layout QA score 1.00.",
        }
    )
    assert review.is_scaffold_review()
    assert not review.is_manual_review()


def test_scaffold_review_shows_pending_label_not_numeric_score() -> None:
    from archium.domain.visual.benchmark import (
        HUMAN_REVIEW_PENDING_LABEL,
        HumanVisualReviewSource,
    )

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
    assert review.human_score_label() == HUMAN_REVIEW_PENDING_LABEL
    assert review.reportable_weighted_score() is None
    assert review.weighted_score() == 4.0
