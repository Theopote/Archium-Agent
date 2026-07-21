"""Problem-driven page quality status (formal gate; not 1–5 averages)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class PageQualityStatus(StrEnum):
    """Formal per-page quality verdict driven by issue severity, not scores."""

    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class IssueSeverity(StrEnum):
    """Three-tier severity for quality findings."""

    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"


class IssueCategory(StrEnum):
    """Human checklist categories A–E."""

    CONTENT = "A_content"
    IMAGE_TEXT = "B_image_text"
    ARCHITECTURAL = "C_architectural"
    LAYOUT_VISUAL = "D_layout_visual"
    DELIVERY_EDITABILITY = "E_delivery_editability"


class QualityIssueSource(StrEnum):
    AUTO = "auto"
    HUMAN = "human"
    CRITIC = "critic"


class ReportingReady(StrEnum):
    """Deck/page readiness for real client reporting (human judgment)."""

    READY = "ready"
    FIXABLE = "fixable"
    DO_NOT_USE = "do_not_use"
    UNSPECIFIED = "unspecified"


class ScoringMode(StrEnum):
    """Whether legacy 1–5 scores are formal or experimental archive only."""

    EXPERIMENTAL = "experimental"
    LEGACY_FORMAL = "legacy_formal"  # historical only; not used for gates


class QualityIssue(DomainModel):
    """A concrete quality finding with code + severity (not a numeric score)."""

    code: str = Field(min_length=1)
    severity: IssueSeverity
    category: IssueCategory | None = None
    message: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: QualityIssueSource = QualityIssueSource.HUMAN
    suggested_fix: str = ""


def derive_page_quality_status(issues: Iterable[QualityIssue]) -> PageQualityStatus:
    """Map issue severities to formal page status (one-vote veto for blockers)."""
    has_blocker = False
    has_major = False
    has_minor = False
    for issue in issues:
        if issue.severity == IssueSeverity.BLOCKER:
            has_blocker = True
        elif issue.severity == IssueSeverity.MAJOR:
            has_major = True
        elif issue.severity == IssueSeverity.MINOR:
            has_minor = True
    if has_blocker:
        return PageQualityStatus.BLOCKED
    if has_major:
        return PageQualityStatus.NEEDS_REVIEW
    if has_minor:
        return PageQualityStatus.PASS_WITH_WARNINGS
    return PageQualityStatus.PASS


def issues_from_free_text(
    *,
    major_problems: list[str],
    minor_problems: list[str],
    source: QualityIssueSource = QualityIssueSource.HUMAN,
) -> list[QualityIssue]:
    """Bridge legacy free-text major/minor lists into QualityIssue rows."""
    issues: list[QualityIssue] = []
    for index, text in enumerate(major_problems):
        cleaned = text.strip()
        if not cleaned:
            continue
        issues.append(
            QualityIssue(
                code=f"HUMAN.MAJOR.{index + 1}",
                severity=IssueSeverity.MAJOR,
                message=cleaned,
                source=source,
            )
        )
    for index, text in enumerate(minor_problems):
        cleaned = text.strip()
        if not cleaned:
            continue
        issues.append(
            QualityIssue(
                code=f"HUMAN.MINOR.{index + 1}",
                severity=IssueSeverity.MINOR,
                message=cleaned,
                source=source,
            )
        )
    return issues
