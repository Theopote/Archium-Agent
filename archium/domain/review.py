"""Presentation review issue model."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, ReviewStatus

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_review_description(description: str) -> str:
    """Collapse whitespace for stable issue fingerprinting."""
    return _WHITESPACE_RE.sub(" ", description.strip()).casefold()


def normalize_rule_code(rule_code: str) -> str:
    """Normalize a machine rule identifier for stable fingerprinting."""
    return rule_code.strip().casefold()


def review_issue_fingerprint(issue: ReviewIssue) -> str:
    """Stable dedupe key for review findings within a workflow pass."""
    slide_key = str(issue.slide_id) if issue.slide_id is not None else ""
    payload = "|".join(
        (
            issue.reviewer_layer.value,
            issue.category.value,
            slide_key,
            normalize_rule_code(issue.rule_code),
            normalize_review_description(issue.description),
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def dedupe_review_issues(
    existing: list[ReviewIssue],
    new_issues: list[ReviewIssue],
) -> list[ReviewIssue]:
    """Merge review issues, keeping the first occurrence of each fingerprint."""
    seen: set[str] = set()
    combined: list[ReviewIssue] = []
    for issue in [*existing, *new_issues]:
        fingerprint = review_issue_fingerprint(issue)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        combined.append(issue)
    return combined


def merge_review_findings(
    existing_issues: list[ReviewIssue],
    new_issues: list[ReviewIssue],
    summarize_for_slides: Callable[[list[ReviewIssue]], list[str]],
) -> dict[str, object]:
    """Append layer findings, deduplicating by review-issue fingerprint."""
    combined = dedupe_review_issues(existing_issues, new_issues)
    return {
        "review_issues": combined,
        "slide_review_issues": summarize_for_slides(combined),
    }


class ReviewIssue(IdentifiedModel, TimestampedModel):
    """A quality or consistency issue found during presentation review."""

    presentation_id: UUID
    slide_id: UUID | None = None
    reviewer_layer: ReviewLayer = ReviewLayer.CONTENT
    category: ReviewCategory
    severity: ReviewSeverity
    rule_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    suggestion: str | None = None
    auto_fixable: bool = False
    status: ReviewStatus = ReviewStatus.OPEN

    def resolve(self) -> None:
        self.status = ReviewStatus.RESOLVED
        self.touch()

    def dismiss(self) -> None:
        self.status = ReviewStatus.DISMISSED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
