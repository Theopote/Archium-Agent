"""Phase 9 rendered-benchmark eligibility and formal review gate status."""

from __future__ import annotations

import pytest
from archium.application.architectural_benchmark_review_store import load_case_review
from archium.application.human_review_gate import evaluate_phase9_human_gate
from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    HumanVisualReview,
    HumanVisualReviewSource,
    ReviewValidity,
)

from tests.benchmark.architectural_slides.artifacts import (
    case_dir,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.render_manifest import (
    pptx_render_path,
    visual_review_eligibility,
)

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.architectural_benchmark,
]


def test_phase9_all_cases_have_pptx_render_and_are_eligible() -> None:
    case_ids = materialized_benchmark_case_ids()
    assert len(case_ids) == HUMAN_REVIEW_FORMAL_TOTAL_CASES
    ineligible: list[str] = []
    for case_id in case_ids:
        directory = case_dir(case_id)
        assert pptx_render_path(directory).is_file(), f"{case_id} missing pptx_render.png"
        eligible, _, blockers = visual_review_eligibility(directory)
        if not eligible:
            ineligible.append(f"{case_id}: {';'.join(blockers)}")
    assert ineligible == []


def test_phase9_formal_gate_not_passed_until_manual_reviews_complete() -> None:
    """Invalidated/placeholder reviews must not satisfy Phase 9 formal gate."""
    reviews: list[HumanVisualReview] = []
    for case_id in materialized_benchmark_case_ids():
        review = load_case_review(case_id)
        if review is not None:
            reviews.append(review)
    result = evaluate_phase9_human_gate(reviews)
    assert result.passed is False
    assert result.completed_valid_count == 0
    assert any("completed valid reviews" in reason for reason in result.reasons)


def test_phase9_gate_requires_thirty_valid_manual_reviews() -> None:
    from datetime import UTC, datetime

    reviews = [
        HumanVisualReview(
            case_id=f"case_{index:03d}",
            source=HumanVisualReviewSource.MANUAL,
            information_hierarchy=4,
            visual_focus=4,
            reading_order=4,
            image_text_relationship=4,
            whitespace_density=4,
            architectural_expression=4,
            aesthetic_finish=4,
            editability=4,
            review_completed=True,
            accepted_for_delivery=True,
            validity=ReviewValidity.VALID,
            reviewer="tester",
            reviewed_at=datetime.now(UTC),
        )
        for index in range(1, 31)
    ]
    # Drop one → must fail completeness.
    partial = evaluate_phase9_human_gate(reviews[:-1])
    assert partial.passed is False
    full = evaluate_phase9_human_gate(reviews)
    assert full.passed is True
    assert full.completed_valid_count == 30
    assert full.accepted_count == 30
