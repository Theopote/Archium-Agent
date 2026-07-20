"""Formal human visual review gate for benchmark and Phase 7/9 sign-off."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD,
    HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    HumanVisualReview,
    ReviewValidity,
)

# Re-export for callers/tests that import thresholds from this module.
__all__ = [
    "HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD",
    "HUMAN_REVIEW_FORMAL_MIN_ACCEPTED",
    "HUMAN_REVIEW_FORMAL_TOTAL_CASES",
    "HumanReviewGateResult",
    "evaluate_benchmark_human_gate",
    "evaluate_phase9_human_gate",
]


@dataclass(frozen=True)
class HumanReviewGateResult:
    """Outcome of evaluating a batch of manual human reviews."""

    passed: bool
    manual_review_count: int
    accepted_count: int
    average_weighted_score: float | None
    has_major_problem_on_accepted: bool
    reasons: list[str]
    completed_valid_count: int = 0

    def summary(self) -> str:
        if self.passed:
            return "人工视觉质量门槛通过"
        return "; ".join(self.reasons) if self.reasons else "人工视觉质量门槛未通过"


def evaluate_benchmark_human_gate(
    reviews: list[HumanVisualReview],
    *,
    total_cases: int = HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    min_accepted: int = HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    average_threshold: float = HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD,
) -> HumanReviewGateResult:
    """Apply WP I formal benchmark criteria to manual reviews only."""
    manual = [review for review in reviews if review.is_manual_review()]
    accepted = [review for review in manual if review.accepted_for_delivery]
    reasons: list[str] = []

    if len(manual) < min_accepted:
        reasons.append(
            f"manual reviews {len(manual)} < required {min_accepted}/{total_cases}"
        )

    average: float | None = None
    if manual:
        average = round(
            sum(review.weighted_score() for review in manual) / len(manual),
            3,
        )
        if average < average_threshold:
            reasons.append(
                f"average score {average:.2f} < threshold {average_threshold:.2f}"
            )

    if len(accepted) < min_accepted:
        reasons.append(
            f"accepted pages {len(accepted)} < required {min_accepted}/{total_cases}"
        )

    major_on_accepted = any(
        review.accepted_for_delivery and review.major_problems for review in manual
    )
    if major_on_accepted:
        reasons.append("accepted page has major_problems")

    passed = not reasons
    return HumanReviewGateResult(
        passed=passed,
        manual_review_count=len(manual),
        accepted_count=len(accepted),
        average_weighted_score=average,
        has_major_problem_on_accepted=major_on_accepted,
        reasons=reasons,
        completed_valid_count=len(manual),
    )


def evaluate_phase9_human_gate(
    reviews: list[HumanVisualReview],
    *,
    total_cases: int = HUMAN_REVIEW_FORMAL_TOTAL_CASES,
    min_accepted: int = HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    average_threshold: float = HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD,
) -> HumanReviewGateResult:
    """Phase 9 formal gate: all pages completed valid manual review + delivery thresholds."""
    valid_completed = [
        review
        for review in reviews
        if review.is_manual_review()
        and review.review_completed
        and review.validity == ReviewValidity.VALID
        and not review.is_invalidated()
    ]
    accepted = [review for review in valid_completed if review.accepted_for_delivery]
    reasons: list[str] = []

    if len(valid_completed) < total_cases:
        reasons.append(
            f"completed valid reviews {len(valid_completed)} < required {total_cases}"
        )

    average: float | None = None
    if valid_completed:
        average = round(
            sum(review.weighted_score() for review in valid_completed) / len(valid_completed),
            3,
        )
        if average < average_threshold:
            reasons.append(
                f"average score {average:.2f} < threshold {average_threshold:.2f}"
            )

    if len(accepted) < min_accepted:
        reasons.append(
            f"accepted pages {len(accepted)} < required {min_accepted}/{total_cases}"
        )

    major_on_accepted = any(review.major_problems for review in accepted)
    if major_on_accepted:
        reasons.append("accepted page has major_problems")

    return HumanReviewGateResult(
        passed=not reasons,
        manual_review_count=len(valid_completed),
        accepted_count=len(accepted),
        average_weighted_score=average,
        has_major_problem_on_accepted=major_on_accepted,
        reasons=reasons,
        completed_valid_count=len(valid_completed),
    )
