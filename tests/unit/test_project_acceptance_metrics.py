"""Unit tests for derived real-project acceptance human metrics."""

from __future__ import annotations

from archium.application.project_acceptance_metrics import (
    derive_acceptance_human_metrics,
    derive_acceptance_human_metrics_from_reviews,
    derive_acceptance_slide_review,
)
from archium.domain.visual.benchmark import HumanVisualReview


def test_derive_metrics_from_clean_deck() -> None:
    derived = derive_acceptance_human_metrics(
        slide_count=20,
        critical_layout_page_count=0,
        error_layout_page_count=0,
        validation_reports=[{"score": 1.0, "issues": []} for _ in range(20)],
        first_generation_seconds=12.0,
    )
    assert derived["major_edit_page_ratio"] == 0.0
    assert derived["exported_page_ratio"] == 1.0
    assert derived["average_human_visual_score"] >= 3.5
    assert derived["user_edit_minutes"] >= 2.0


def test_derive_metrics_counts_major_and_minor_pages() -> None:
    reports = [
        {"score": 0.4, "issues": [{"severity": "error", "message": "overflow"}]},
        {"score": 0.9, "issues": [{"severity": "warning", "message": "tight"}]},
        {"score": 1.0, "issues": []},
    ]
    derived = derive_acceptance_human_metrics(
        slide_count=3,
        critical_layout_page_count=0,
        error_layout_page_count=1,
        validation_reports=reports,
        first_generation_seconds=8.0,
    )
    assert derived["major_edit_page_ratio"] == 0.333
    assert derived["minor_edit_page_ratio"] == 0.333


def test_derive_metrics_from_reviews_overrides_layout_fallback() -> None:
    fallback = derive_acceptance_human_metrics(
        slide_count=2,
        critical_layout_page_count=0,
        error_layout_page_count=0,
        validation_reports=[{"score": 0.2, "issues": []}, {"score": 0.2, "issues": []}],
        first_generation_seconds=5.0,
    )
    reviews = [
        HumanVisualReview(
            case_id="slide-a",
            information_hierarchy=5,
            visual_focus=5,
            reading_order=5,
            image_text_relationship=5,
            whitespace_density=5,
            architectural_expression=5,
            aesthetic_finish=5,
            editability=5,
            accepted=True,
            reviewer_notes="manual review",
        ),
        HumanVisualReview(
            case_id="slide-b",
            information_hierarchy=4,
            visual_focus=4,
            reading_order=4,
            image_text_relationship=4,
            whitespace_density=4,
            architectural_expression=4,
            aesthetic_finish=4,
            editability=4,
            major_problems=["hero cropped"],
            accepted=False,
            reviewer_notes="needs fix",
        ),
    ]
    derived = derive_acceptance_human_metrics_from_reviews(
        reviews,
        slide_count=2,
        fallback=fallback,
    )
    assert derived["average_human_visual_score"] == 4.5
    assert derived["exported_page_ratio"] == 0.5
    assert derived["major_edit_page_ratio"] == 0.5


def test_derive_acceptance_slide_review_from_layout_qa() -> None:
    from uuid import uuid4

    review = derive_acceptance_slide_review(
        uuid4(),
        layout_score=0.9,
        layout_valid=True,
        has_blocking_issues=False,
    )
    assert review.accepted
    assert review.weighted_score() >= 3.5
    assert "Acceptance rehearsal" in review.reviewer_notes
