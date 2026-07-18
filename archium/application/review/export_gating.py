"""Export blocking rules for open review issues."""

from __future__ import annotations

from archium.application.visual_qa_service import asset_load_rule_codes
from archium.domain.enums import ReviewSeverity, ReviewStatus
from archium.domain.review import ReviewIssue


def export_blocking_open_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    """Return open review issues that should block formal export."""
    asset_load_rules = asset_load_rule_codes()
    blocking: list[ReviewIssue] = []
    for issue in issues:
        if issue.status != ReviewStatus.OPEN:
            continue
        if issue.severity == ReviewSeverity.CRITICAL:
            blocking.append(issue)
            continue
        if issue.severity == ReviewSeverity.HIGH and issue.rule_code in asset_load_rules:
            blocking.append(issue)
    return blocking


def critical_export_block_messages(
    issues: list[ReviewIssue],
    *,
    block_enabled: bool,
) -> list[str]:
    """Return workflow error messages when open review issues should block export."""
    if not block_enabled:
        return []
    return [
        f"[{issue.category.value}] {issue.title}: {issue.description}"
        for issue in export_blocking_open_issues(issues)
    ]
