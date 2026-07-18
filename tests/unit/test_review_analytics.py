"""Tests for review issue analytics keyed by rule_code."""

from __future__ import annotations

from uuid import uuid4

from archium.application.review_analytics import summarize_rule_codes
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, ReviewStatus
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import (
    ReviewRepairStrategy,
    ReviewRuleCode,
)


def _issue(
    *,
    rule_code: str,
    status: ReviewStatus = ReviewStatus.OPEN,
) -> ReviewIssue:
    return ReviewIssue(
        presentation_id=uuid4(),
        slide_id=uuid4(),
        reviewer_layer=ReviewLayer.CONTENT,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.MEDIUM,
        rule_code=rule_code,
        title="测试问题",
        description="测试描述",
        status=status,
    )


def test_summarize_rule_codes_groups_counts_and_strategy() -> None:
    issues = [
        _issue(rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS),
        _issue(
            rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
            status=ReviewStatus.DISMISSED,
        ),
        _issue(
            rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
            status=ReviewStatus.RESOLVED,
        ),
    ]

    stats = summarize_rule_codes(issues)

    assert len(stats) == 2
    layout_stats = next(item for item in stats if item.rule_code == ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS)
    assert layout_stats.total == 2
    assert layout_stats.open == 1
    assert layout_stats.dismissed == 1
    assert layout_stats.repair_strategy == ReviewRepairStrategy.TIERED_LAYOUT
    assert layout_stats.dismiss_rate == 1.0

    evidence_stats = next(
        item for item in stats if item.rule_code == ReviewRuleCode.EVIDENCE_MISSING_CITATION
    )
    assert evidence_stats.resolved == 1
    assert evidence_stats.repair_strategy == ReviewRepairStrategy.LLM_CONTENT
    assert evidence_stats.dismiss_rate == 0.0
