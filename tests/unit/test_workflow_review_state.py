"""Unit tests for workflow review state merging."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, ReviewStatus
from archium.domain.review import ReviewIssue
from archium.workflow.nodes import PresentationWorkflowNodes
from archium.workflow.state import PresentationWorkflowState


class _StubReviewer:
    @staticmethod
    def summarize_for_slides(issues: list[ReviewIssue]) -> list[str]:
        return [issue.title for issue in issues if issue.slide_id is not None]


def _issue(title: str) -> ReviewIssue:
    return ReviewIssue(
        presentation_id=uuid4(),
        reviewer_layer=ReviewLayer.CONTENT,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.HIGH,
        status=ReviewStatus.OPEN,
        title=title,
        description=f"{title} description",
    )


def test_review_issue_merge_does_not_duplicate_existing_issues() -> None:
    """Layer nodes must append only new findings, never existing + existing + new."""
    reviewer = _StubReviewer()
    state: PresentationWorkflowState = {"review_issues": [_issue("first")]}

    first_pass = PresentationWorkflowNodes._merge_review_findings(
        state,
        [_issue("second")],
        reviewer,  # type: ignore[arg-type]
    )
    assert len(first_pass["review_issues"]) == 2

    duplicated = list(state.get("review_issues", [])) + list(state.get("review_issues", []))
    duplicated.extend([_issue("second")])
    assert len(duplicated) == 3

    second_pass = PresentationWorkflowNodes._merge_review_findings(
        {**state, **first_pass},  # type: ignore[arg-type]
        [_issue("third")],
        reviewer,  # type: ignore[arg-type]
    )
    assert len(second_pass["review_issues"]) == 3
