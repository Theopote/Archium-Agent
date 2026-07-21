"""Convert scene semantic QA findings to quality issues and compare proposals."""

from __future__ import annotations

from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.quality_issue_catalog import default_severity_for_auto_code
from archium.domain.visual.scene_change_proposal import ProposalQAComparison
from archium.domain.visual.scene_qa import SceneSemanticCheckCode


def findings_to_quality_issues(findings: list[SlideSemanticFinding]) -> list[QualityIssue]:
    """Map RenderScene semantic findings to formal quality issues."""
    issues: list[QualityIssue] = []
    for finding in findings:
        category = _category_for_code(finding.check_code)
        issues.append(
            QualityIssue(
                code=finding.check_code,
                severity=default_severity_for_auto_code(finding.check_code),
                category=category,
                message=finding.title or finding.description,
                evidence=list(finding.evidence_refs or []),
                source=QualityIssueSource.AUTO,
                suggested_fix=finding.suggestion or "",
            )
        )
    return issues


def compare_proposal_qa(
  before: list[QualityIssue],
  after: list[QualityIssue],
) -> ProposalQAComparison:
    """Compute resolved / remaining / introduced issues between two QA snapshots."""
    before_keys = {_issue_key(issue) for issue in before}
    after_keys = {_issue_key(issue) for issue in after}
    resolved = [issue for issue in before if _issue_key(issue) not in after_keys]
    remaining = [issue for issue in after if _issue_key(issue) in before_keys]
    introduced = [issue for issue in after if _issue_key(issue) not in before_keys]
    return ProposalQAComparison(
        before=before,
        after=after,
        resolved=resolved,
        remaining=remaining,
        introduced=introduced,
    )


def proposal_introduces_blocker(comparison: ProposalQAComparison) -> bool:
    """Return True when the proposal adds a blocker-level issue."""
    return any(issue.severity == IssueSeverity.BLOCKER for issue in comparison.introduced)


def _issue_key(issue: QualityIssue) -> tuple[str, tuple[str, ...]]:
    return (issue.code, tuple(sorted(issue.evidence)))


def _category_for_code(code: str) -> IssueCategory:
    if code in {
        SceneSemanticCheckCode.AI_IMAGE_PRESENTED_AS_REAL_PROJECT,
        SceneSemanticCheckCode.STOCK_IMAGE_PRESENTED_AS_PROJECT,
    }:
        return IssueCategory.IMAGE_TEXT
    if code.startswith("SEMANTIC.DRAWING"):
        return IssueCategory.ARCHITECTURAL
    if code.startswith("LAYOUT."):
        return IssueCategory.LAYOUT_VISUAL
    return IssueCategory.DELIVERY_EDITABILITY
