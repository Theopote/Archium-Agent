"""Formal human exception-review gate — problem-driven, not 1–5 averages."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD,
    HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS,
    HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    HumanVisualReview,
    ReviewValidity,
)
from archium.domain.visual.page_quality import PageQualityStatus, ReportingReady

# Re-export for callers/tests that import thresholds from this module.
__all__ = [
    "HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD",
    "HUMAN_REVIEW_FORMAL_MIN_ACCEPTED",
    "HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS",
    "HUMAN_REVIEW_FORMAL_TOTAL_CASES",
    "HumanReviewGateResult",
    "evaluate_benchmark_human_gate",
    "evaluate_phase9_human_gate",
    "count_page_quality_statuses",
]


@dataclass(frozen=True)
class HumanReviewGateResult:
    """Outcome of evaluating problem-driven human exception reviews."""

    passed: bool
    manual_review_count: int
    accepted_count: int
    average_weighted_score: float | None  # experimental only; never gates
    has_major_problem_on_accepted: bool
    reasons: list[str]
    completed_valid_count: int = 0
    blocked_count: int = 0
    needs_review_count: int = 0
    page_quality_status_counts: dict[str, int] | None = None

    def summary(self) -> str:
        if self.passed:
            return "人工异常复核质量门槛通过（问题驱动）"
        return "; ".join(self.reasons) if self.reasons else "人工异常复核质量门槛未通过"


def count_page_quality_statuses(reviews: list[HumanVisualReview]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for review in reviews:
        if not review.is_manual_review() or review.is_invalidated():
            continue
        status = review.derived_page_quality_status()
        counts[status.value] += 1
    return {status.value: counts.get(status.value, 0) for status in PageQualityStatus}


def _experimental_average(reviews: list[HumanVisualReview]) -> float | None:
    """Compute legacy average for research export only — does not gate."""
    if not reviews:
        return None
    return round(sum(review.weighted_score() for review in reviews) / len(reviews), 3)


def evaluate_benchmark_human_gate(
    reviews: list[HumanVisualReview],
    *,
    total_cases: int = HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    min_accepted: int = HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    min_exception_reviews: int = HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS,
    average_threshold: float | None = None,
) -> HumanReviewGateResult:
    """Formal benchmark gate: exception reviews + no blockers on accepted pages.

    ``average_threshold`` is ignored (kept for call-site compatibility).
    Experimental 1–5 averages are reported but never used to pass/fail.
    """
    del average_threshold  # retired as formal criterion
    manual = [
        review
        for review in reviews
        if review.is_manual_review() and not review.is_invalidated()
    ]
    exception = [review for review in manual if review.is_exception_review()]
    accepted = [
        review
        for review in exception
        if review.accepted_for_delivery
        and review.reporting_ready
        in {ReportingReady.READY, ReportingReady.FIXABLE, ReportingReady.UNSPECIFIED}
        and review.derived_page_quality_status()
        in {PageQualityStatus.PASS, PageQualityStatus.PASS_WITH_WARNINGS}
    ]
    reasons: list[str] = []
    status_counts = count_page_quality_statuses(exception)

    if len(exception) < min_exception_reviews:
        reasons.append(
            f"exception reviews {len(exception)} < required "
            f"{min_exception_reviews} (pilot / spot-check floor)"
        )

    blocked_accepted = [
        review
        for review in exception
        if review.accepted_for_delivery
        and (
            review.has_blocker_issues()
            or review.derived_page_quality_status() == PageQualityStatus.BLOCKED
            or review.reporting_ready == ReportingReady.DO_NOT_USE
        )
    ]
    if blocked_accepted:
        reasons.append("accepted page has blocker / BLOCKED / do_not_use")

    major_on_accepted = any(
        review.accepted_for_delivery
        and (
            review.major_problems
            or review.derived_page_quality_status() == PageQualityStatus.NEEDS_REVIEW
        )
        for review in exception
    )
    if major_on_accepted:
        reasons.append("accepted page has major issues / NEEDS_REVIEW")

    # Full-suite acceptance still tracked; not required until enough exception reviews exist.
    if len(exception) >= total_cases and len(accepted) < min_accepted:
        reasons.append(
            f"accepted deliverable pages {len(accepted)} < required {min_accepted}/{total_cases}"
        )

    return HumanReviewGateResult(
        passed=not reasons,
        manual_review_count=len(exception),
        accepted_count=len(accepted),
        average_weighted_score=_experimental_average(exception),
        has_major_problem_on_accepted=major_on_accepted,
        reasons=reasons,
        completed_valid_count=len(exception),
        blocked_count=status_counts.get(PageQualityStatus.BLOCKED.value, 0),
        needs_review_count=status_counts.get(PageQualityStatus.NEEDS_REVIEW.value, 0),
        page_quality_status_counts=status_counts,
    )


def evaluate_phase9_human_gate(
    reviews: list[HumanVisualReview],
    *,
    total_cases: int = HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    min_accepted: int = HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    average_threshold: float | None = None,
) -> HumanReviewGateResult:
    """Phase 9: all pages completed valid exception review; no score average."""
    del average_threshold
    valid_completed = [
        review
        for review in reviews
        if review.is_exception_review()
        and review.validity == ReviewValidity.VALID
    ]
    accepted = [
        review
        for review in valid_completed
        if review.accepted_for_delivery
        and review.derived_page_quality_status()
        in {PageQualityStatus.PASS, PageQualityStatus.PASS_WITH_WARNINGS}
        and review.reporting_ready != ReportingReady.DO_NOT_USE
    ]
    reasons: list[str] = []
    status_counts = count_page_quality_statuses(valid_completed)

    if len(valid_completed) < total_cases:
        reasons.append(
            f"completed valid exception reviews {len(valid_completed)} "
            f"< required {total_cases}"
        )

    if len(accepted) < min_accepted:
        reasons.append(
            f"accepted pages {len(accepted)} < required {min_accepted}/{total_cases}"
        )

    major_on_accepted = any(
        review.major_problems
        or review.derived_page_quality_status() == PageQualityStatus.NEEDS_REVIEW
        or review.has_blocker_issues()
        for review in accepted
    )
    if major_on_accepted:
        reasons.append("accepted page has major_problems or NEEDS_REVIEW/blocker")

    blocked_on_accepted = any(
        review.derived_page_quality_status() == PageQualityStatus.BLOCKED for review in accepted
    )
    if blocked_on_accepted:
        reasons.append("accepted page is BLOCKED")

    return HumanReviewGateResult(
        passed=not reasons,
        manual_review_count=len(valid_completed),
        accepted_count=len(accepted),
        average_weighted_score=_experimental_average(valid_completed),
        has_major_problem_on_accepted=major_on_accepted,
        reasons=reasons,
        completed_valid_count=len(valid_completed),
        blocked_count=status_counts.get(PageQualityStatus.BLOCKED.value, 0),
        needs_review_count=status_counts.get(PageQualityStatus.NEEDS_REVIEW.value, 0),
        page_quality_status_counts=status_counts,
    )
