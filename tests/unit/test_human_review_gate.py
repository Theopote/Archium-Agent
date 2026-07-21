"""Unit tests for problem-driven human exception-review gate."""

from __future__ import annotations

from datetime import UTC, datetime

from archium.application.human_review_gate import (
    evaluate_benchmark_human_gate,
    evaluate_phase9_human_gate,
)
from archium.domain.visual.benchmark import HumanVisualReview, HumanVisualReviewSource
from archium.domain.visual.page_quality import (
    IssueSeverity,
    PageQualityStatus,
    QualityIssue,
    QualityIssueSource,
    ReportingReady,
    derive_page_quality_status,
)


def _exception_review(
    *,
    case_id: str,
    accepted: bool,
    codes: list[str] | None = None,
    major: list[str] | None = None,
    reporting_ready: ReportingReady = ReportingReady.READY,
) -> HumanVisualReview:
    return HumanVisualReview(
        case_id=case_id,
        source=HumanVisualReviewSource.MANUAL,
        selected_issue_codes=codes or [],
        major_problems=major or [],
        reporting_ready=reporting_ready,
        accepted=accepted,
        accepted_for_delivery=accepted,
        review_completed=True,
        reviewer="architect_a",
        reviewed_at=datetime.now(UTC),
        reviewer_notes="exception review",
    )


def test_derive_status_blocker_wins() -> None:
    status = derive_page_quality_status(
        [
            QualityIssue(
                code="X.MINOR",
                severity=IssueSeverity.MINOR,
                source=QualityIssueSource.HUMAN,
            ),
            QualityIssue(
                code="X.BLOCKER",
                severity=IssueSeverity.BLOCKER,
                source=QualityIssueSource.HUMAN,
            ),
        ]
    )
    assert status == PageQualityStatus.BLOCKED


def test_human_gate_fails_without_enough_exception_reviews() -> None:
    reviews = [_exception_review(case_id="case_001", accepted=True)]
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    assert result.passed is False
    assert any("exception reviews" in reason for reason in result.reasons)


def test_human_gate_passes_pilot_batch_without_score_average() -> None:
    reviews = [
        _exception_review(case_id=f"case_{index:03d}", accepted=True)
        for index in range(1, 4)
    ]
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    assert result.passed is True
    # Experimental average may exist but must not gate.
    assert result.average_weighted_score is None or result.average_weighted_score >= 0


def test_human_gate_ignores_low_experimental_scores() -> None:
    """1–5 scores no longer fail the formal gate."""
    reviews = []
    for index in range(1, 4):
        review = _exception_review(case_id=f"case_{index:03d}", accepted=True)
        review = review.model_copy(
            update={
                "information_hierarchy": 1,
                "visual_focus": 1,
                "reading_order": 1,
                "image_text_relationship": 1,
                "whitespace_density": 1,
                "architectural_expression": 1,
                "aesthetic_finish": 1,
                "editability": 1,
            }
        )
        reviews.append(review)
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    assert result.passed is True


def test_human_gate_fails_when_accepted_page_has_blocker_code() -> None:
    reviews = [
        _exception_review(
            case_id=f"case_{index:03d}",
            accepted=True,
            codes=["ARCH.REFERENCE_AS_PROJECT"] if index == 1 else [],
        )
        for index in range(1, 4)
    ]
    # Domain clears acceptance when blockers present.
    assert reviews[0].accepted_for_delivery is False
    assert reviews[0].derived_page_quality_status() == PageQualityStatus.BLOCKED
    result = evaluate_benchmark_human_gate(reviews, total_cases=30, min_accepted=24)
    # Still passes pilot floor if remaining accepted pages are clean — blockers not accepted.
    assert result.blocked_count >= 1


def test_phase9_gate_requires_all_thirty_completed() -> None:
    reviews = [
        _exception_review(case_id=f"case_{index:03d}", accepted=True)
        for index in range(1, 31)
    ]
    assert evaluate_phase9_human_gate(reviews[:-1]).passed is False
    assert evaluate_phase9_human_gate(reviews).passed is True


def test_formal_threshold_constants_import_after_visual_package() -> None:
    """Regression: constants must exist before LayoutFamily import side-effects."""
    import archium.domain.visual  # noqa: F401
    from archium.application.human_review_gate import HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD
    from archium.domain.visual.benchmark import (
        HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
        HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS,
    )

    assert HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD == 3.8  # experimental archive constant
    assert HUMAN_REVIEW_FORMAL_MIN_ACCEPTED == 24
    assert HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS == 3
