"""Unit tests for workflow review state merging."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, ReviewStatus
from archium.domain.review import (
    ReviewIssue,
    dedupe_review_issues,
    merge_review_findings,
    review_issue_fingerprint,
)
from archium.domain.review_rules import ReviewRuleCode


class _StubReviewer:
    @staticmethod
    def summarize_for_slides(issues: list[ReviewIssue]) -> list[str]:
        return [issue.title for issue in issues if issue.slide_id is not None]


def _issue(
    title: str,
    *,
    rule_code: str = ReviewRuleCode.LEGACY_UNSPECIFIED,
    slide_id: UUID | None = None,
    layer: ReviewLayer = ReviewLayer.CONTENT,
    description: str | None = None,
) -> ReviewIssue:
    return ReviewIssue(
        presentation_id=uuid4(),
        slide_id=slide_id,
        reviewer_layer=layer,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.HIGH,
        status=ReviewStatus.OPEN,
        rule_code=rule_code,
        title=title,
        description=description or f"{title} description",
    )


def test_review_issue_merge_does_not_duplicate_existing_issues() -> None:
    """Layer nodes must append only new findings, never existing + existing + new."""
    summarize = _StubReviewer.summarize_for_slides
    state_issues = [_issue("first")]

    first_pass = merge_review_findings(state_issues, [_issue("second")], summarize)
    assert len(first_pass["review_issues"]) == 2

    duplicated = list(state_issues) + list(state_issues)
    duplicated.extend([_issue("second")])
    assert len(duplicated) == 3

    second_pass = merge_review_findings(
        first_pass["review_issues"],  # type: ignore[arg-type]
        [_issue("third")],
        summarize,
    )
    assert len(second_pass["review_issues"]) == 3


def test_review_issue_fingerprint_deduplicates_same_rule() -> None:
    slide_id = uuid4()
    original = _issue(
        "缺少引用来源",
        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
        slide_id=slide_id,
        layer=ReviewLayer.EVIDENCE,
        description="第 2 页缺少引用来源",
    )
    duplicate = _issue(
        "缺少引用来源",
        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
        slide_id=slide_id,
        layer=ReviewLayer.EVIDENCE,
        description="第 2 页缺少引用来源",
    )
    assert review_issue_fingerprint(original) == review_issue_fingerprint(duplicate)

    merged = dedupe_review_issues([original], [duplicate])
    assert len(merged) == 1
    assert merged[0].id == original.id


def test_review_issue_fingerprint_deduplicates_by_rule_code_not_title() -> None:
    slide_id = uuid4()
    original = _issue(
        "缺少引用来源",
        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
        slide_id=slide_id,
        layer=ReviewLayer.EVIDENCE,
        description="第 2 页缺少引用来源",
    )
    renamed = _issue(
        "未标注资料出处",
        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
        slide_id=slide_id,
        layer=ReviewLayer.EVIDENCE,
        description="第 2 页缺少引用来源",
    )

    assert review_issue_fingerprint(original) == review_issue_fingerprint(renamed)
    merged = dedupe_review_issues([original], [renamed])
    assert len(merged) == 1


def test_review_issue_fingerprint_keeps_distinct_layers() -> None:
    slide_id = uuid4()
    content_issue = _issue(
        "文本密度过高",
        rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
        slide_id=slide_id,
        layer=ReviewLayer.CONTENT,
    )
    layout_issue = _issue(
        "文本密度过高",
        rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
        slide_id=slide_id,
        layer=ReviewLayer.LAYOUT,
        description="第 3 页文本密度过高",
    )

    merged = dedupe_review_issues([content_issue], [layout_issue])
    assert len(merged) == 2


def test_merge_review_findings_skips_reloaded_duplicates() -> None:
    """Simulate a reviewer returning an issue already present in graph state."""
    existing = _issue(
        "交通流线图缺少颜色图例提示",
        rule_code=ReviewRuleCode.ARCH_FLOW_DIAGRAM_MISSING_LEGEND,
        layer=ReviewLayer.ARCHITECTURAL,
    )
    reloaded = _issue(
        "交通流线图缺少颜色图例提示",
        rule_code=ReviewRuleCode.ARCH_FLOW_DIAGRAM_MISSING_LEGEND,
        layer=ReviewLayer.ARCHITECTURAL,
        description=existing.description,
    )

    merged = merge_review_findings([existing], [reloaded], _StubReviewer.summarize_for_slides)
    assert len(merged["review_issues"]) == 1
