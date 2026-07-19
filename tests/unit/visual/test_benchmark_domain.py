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
