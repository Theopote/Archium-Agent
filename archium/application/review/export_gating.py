"""Export blocking rules for open review issues.

Reasons about ``IssueSeverity`` (DOM-004 gate vocabulary) via
``review_to_gate``; ``ReviewSeverity`` remains the persisted field.
"""

from __future__ import annotations

from archium.application.visual_qa_service import asset_load_rule_codes
from archium.domain.enums import ReviewStatus
from archium.domain.review import ReviewIssue
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.severity import is_gate_blocker, review_to_gate


def export_blocking_open_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    """Return open review issues that should block formal export."""
    from archium.domain.review_rules import ReviewRuleCode

    asset_load_rules = asset_load_rule_codes()
    scene_block_rules = frozenset(
        {
            ReviewRuleCode.SEMANTIC_IMAGE_NOT_RENDERED,
            ReviewRuleCode.SEMANTIC_AI_IMAGE_PRESENTED_AS_REAL_PROJECT,
            ReviewRuleCode.SEMANTIC_STOCK_IMAGE_PRESENTED_AS_PROJECT,
            ReviewRuleCode.SEMANTIC_TEXT_OVERFLOW,
            ReviewRuleCode.SEMANTIC_SCENE_PPTX_NODE_MISMATCH,
            ReviewRuleCode.SEMANTIC_DRAWING_COVER_MODE_FORBIDDEN,
            ReviewRuleCode.POST_RENDER_BLANK_PAGE,
            ReviewRuleCode.POST_RENDER_ALL_PAGES_IDENTICAL,
            ReviewRuleCode.POST_RENDER_BLACK_BLOCK,
            ReviewRuleCode.POST_RENDER_IMAGE_NOT_LOADED,
            ReviewRuleCode.POST_RENDER_PNG_PPTX_DIFF,
        }
    )
    blocking: list[ReviewIssue] = []
    for issue in issues:
        if issue.status != ReviewStatus.OPEN:
            continue
        gate = review_to_gate(issue.severity)
        if is_gate_blocker(gate):
            blocking.append(issue)
            continue
        if gate == IssueSeverity.MAJOR and issue.rule_code in asset_load_rules:
            blocking.append(issue)
            continue
        if gate == IssueSeverity.MAJOR and issue.rule_code in scene_block_rules:
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
