"""Tests for problem-driven page quality status and issue catalog."""

from __future__ import annotations

from archium.domain.visual.page_quality import (
    IssueSeverity,
    PageQualityStatus,
    QualityIssue,
    QualityIssueSource,
    derive_page_quality_status,
)
from archium.domain.visual.quality_issue_catalog import (
    HUMAN_CHECKLIST_BY_CODE,
    default_severity_for_auto_code,
)


def test_status_ladder() -> None:
    assert (
        derive_page_quality_status([]) == PageQualityStatus.PASS
    )
    assert (
        derive_page_quality_status(
            [
                QualityIssue(
                    code="M",
                    severity=IssueSeverity.MINOR,
                    source=QualityIssueSource.AUTO,
                )
            ]
        )
        == PageQualityStatus.PASS_WITH_WARNINGS
    )
    assert (
        derive_page_quality_status(
            [
                QualityIssue(
                    code="J",
                    severity=IssueSeverity.MAJOR,
                    source=QualityIssueSource.HUMAN,
                )
            ]
        )
        == PageQualityStatus.NEEDS_REVIEW
    )


def test_catalog_veto_and_auto_map() -> None:
    assert HUMAN_CHECKLIST_BY_CODE["ARCH.REFERENCE_AS_PROJECT"].veto is True
    assert default_severity_for_auto_code("POST_RENDER.BLANK_PAGE") == IssueSeverity.BLOCKER
    assert default_severity_for_auto_code("DECK.REPEATED_LAYOUT_FAMILY") == IssueSeverity.MINOR
    assert default_severity_for_auto_code("CRITIC.HERO_WEAK") == IssueSeverity.MAJOR
