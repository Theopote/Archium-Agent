"""Unit tests for formal human review gate."""

from __future__ import annotations

from datetime import UTC, datetime

from archium.application.human_review_gate import evaluate_benchmark_human_gate
from archium.domain.visual.benchmark import HumanVisualReview, HumanVisualReviewSource


def _manual_review(
    *,
    case_id: str,
    accepted: bool,
    score: int = 4,
    major: list[str] | None = None,
) -> HumanVisualReview:
    return HumanVisualReview(
        case_id=case_id,
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=score,
        visual_focus=score,
        reading_order=score,
        image_text_relationship=score,
        whitespace_density=score,
        architectural_expression=score,
        aesthetic_finish=score,
        editability=score,
        major_problems=major or [],
        accepted=accepted,
        reviewer="architect_a",
        reviewed_at=datetime.now(UTC),
        reviewer_notes="manual session",
    )


def test_human_gate_fails_without_enough_manual_reviews() -> None:
    reviews = [_manual_review(case_id="case_001", accepted=True)]
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    assert result.passed is False
    assert any("manual reviews" in reason for reason in result.reasons)


def test_human_gate_passes_with_strong_manual_batch() -> None:
    reviews = [
        _manual_review(case_id=f"case_{index:03d}", accepted=True, score=4)
        for index in range(1, 25)
    ]
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    assert result.passed is True
    assert result.average_weighted_score is not None
    assert result.average_weighted_score >= 3.8


def test_human_gate_fails_when_accepted_page_has_major_problem() -> None:
    reviews = [
        _manual_review(
            case_id=f"case_{index:03d}",
            accepted=True,
            score=4,
            major=["drawing cropped"] if index == 1 else [],
        )
        for index in range(1, 25)
    ]
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    # Domain model clears accepted_for_delivery when major_problems are present.
    assert result.passed is False
    assert result.accepted_count == 23
    assert any("accepted pages" in reason for reason in result.reasons)


def test_phase9_gate_requires_all_thirty_completed() -> None:
    from archium.application.human_review_gate import evaluate_phase9_human_gate

    reviews = [
        _manual_review(case_id=f"case_{index:03d}", accepted=True, score=4)
        for index in range(1, 31)
    ]
    assert evaluate_phase9_human_gate(reviews[:-1]).passed is False
    assert evaluate_phase9_human_gate(reviews).passed is True


def test_formal_threshold_constants_import_after_visual_package() -> None:
    """Regression: constants must exist before LayoutFamily import side-effects."""
    import archium.domain.visual  # noqa: F401

    from archium.application.human_review_gate import HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD
    from archium.domain.visual.benchmark import HUMAN_REVIEW_FORMAL_MIN_ACCEPTED

    assert HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD == 3.8
    assert HUMAN_REVIEW_FORMAL_MIN_ACCEPTED == 24
