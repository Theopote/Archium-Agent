"""Unit tests for visual QA confidence policy."""

from __future__ import annotations

from archium.application.visual_qa_policy import (
    CONFIDENCE_EMIT_FORMAL,
    CONFIDENCE_EMIT_SUSPECTED,
    DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE,
    decide_check_issue,
)
from archium.domain.visual_qa import VisualQACheck


def test_decide_check_issue_emits_formal_at_high_confidence() -> None:
    check = VisualQACheck(
        check_name="image_dimensions",
        passed=False,
        confidence=CONFIDENCE_EMIT_FORMAL,
        summary="分辨率不足",
    )
    decision = decide_check_issue(check)
    assert decision.emit is True
    assert decision.requires_confirmation is False


def test_decide_check_issue_emits_suspected_in_mid_band() -> None:
    check = VisualQACheck(
        check_name="blank_margins",
        passed=False,
        confidence=CONFIDENCE_EMIT_SUSPECTED + 0.05,
        summary="空白边距偏大",
    )
    decision = decide_check_issue(check)
    assert decision.emit is True
    assert decision.requires_confirmation is True


def test_decide_check_issue_suppresses_low_confidence() -> None:
    check = VisualQACheck(
        check_name="north_arrow",
        passed=False,
        confidence=CONFIDENCE_EMIT_SUSPECTED - 0.01,
        summary="未检测到指北针",
    )
    decision = decide_check_issue(check)
    assert decision.emit is False
    assert decision.requires_confirmation is False


def test_drawing_type_mismatch_threshold_is_075() -> None:
    assert DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE == 0.75
