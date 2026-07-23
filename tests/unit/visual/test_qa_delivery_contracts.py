"""QA / delivery gate contracts."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.review.export_gating import export_blocking_open_issues
from archium.application.review.scene_render_qa import _review_severity_for_check
from archium.application.visual.post_render_qa_service import run_post_render_qa
from archium.application.visual.scene_deterministic_qa_service import _dedupe_issues
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, ReviewStatus
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.visual.deck_qa import DeckQAFinding, DeckQAReport
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.scene_qa import PostRenderCheckCode, SceneSemanticCheckCode


def test_dedupe_keeps_highest_severity() -> None:
    issues = _dedupe_issues(
        [
            QualityIssue(
                code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
                message="major path",
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.ARCHITECTURAL,
                evidence=["plan"],
                source=QualityIssueSource.AUTO,
            ),
            QualityIssue(
                code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
                message="blocker path",
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                evidence=["plan"],
                source=QualityIssueSource.AUTO,
            ),
        ]
    )
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.BLOCKER


def test_review_severity_prefers_catalog_blocker() -> None:
    severity = _review_severity_for_check(
        SceneSemanticCheckCode.TEXT_OVERFLOW,
        "medium",
    )
    assert severity == ReviewSeverity.CRITICAL


def test_export_gating_blocks_post_render_black_block() -> None:
    issue = ReviewIssue(
        presentation_id=uuid4(),
        slide_id=uuid4(),
        reviewer_layer=ReviewLayer.LAYOUT,
        category=ReviewCategory.VISUAL,
        severity=ReviewSeverity.HIGH,
        rule_code=ReviewRuleCode.POST_RENDER_BLACK_BLOCK,
        title="黑块",
        description="大面积黑块",
        status=ReviewStatus.OPEN,
    )
    assert export_blocking_open_issues([issue]) == [issue]


def test_post_render_missing_image_emits_finding(tmp_path: Path) -> None:
    slide_id = uuid4()
    missing = tmp_path / "missing.png"
    report = run_post_render_qa(
        uuid4(),
        [(slide_id, missing)],
        slide_orders={slide_id: 0},
    )
    assert report.checked_slide_count == 1
    assert any(
        finding.check_code == PostRenderCheckCode.IMAGE_NOT_LOADED
        for finding in report.findings
    )


def test_deck_qa_report_blocker_count() -> None:
    report = DeckQAReport(
        findings=[
            DeckQAFinding(
                rule_code="DECK.X",
                severity=LayoutIssueSeverity.CRITICAL,
                message="critical",
            ),
            DeckQAFinding(
                rule_code="DECK.Y",
                severity=LayoutIssueSeverity.WARNING,
                message="warn",
            ),
            DeckQAFinding(
                rule_code="DECK.Z",
                severity=LayoutIssueSeverity.ERROR,
                message="error",
            ),
        ]
    )
    # DOM-004: only Layout CRITICAL maps to gate BLOCKER (ERROR → MAJOR).
    assert report.blocker_count == 1
    assert report.model_dump(mode="json")["blocker_count"] == 1
