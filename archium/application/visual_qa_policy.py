"""Confidence policy for heuristic visual QA findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.visual_qa_calibration import (
    DEFAULT_REPORT_PATH,
    formal_emit_rule_codes,
)
from archium.domain.visual_qa import VisualQACheck

CONFIDENCE_EMIT_FORMAL = 0.85
CONFIDENCE_EMIT_SUSPECTED = 0.60
DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE = 0.75


@dataclass(frozen=True)
class VisualQAIssueDecision:
    """Whether a failed check should become a review issue."""

    emit: bool
    requires_confirmation: bool


def decide_check_issue(
    check: VisualQACheck,
    *,
    rule_code: str,
    calibration_report_path: Path | None = None,
) -> VisualQAIssueDecision:
    """Map a failed heuristic check to issue visibility.

    Rules that have not met calibration precision targets always emit as suspected
    (requires_confirmation), even at high confidence. They never block export.
    """
    if check.passed:
        return VisualQAIssueDecision(emit=False, requires_confirmation=False)

    confidence = check.confidence
    report_path = calibration_report_path or DEFAULT_REPORT_PATH
    formal_eligible = rule_code in formal_emit_rule_codes(report_path)

    if confidence >= CONFIDENCE_EMIT_FORMAL and formal_eligible:
        return VisualQAIssueDecision(emit=True, requires_confirmation=False)
    if confidence >= CONFIDENCE_EMIT_SUSPECTED:
        return VisualQAIssueDecision(emit=True, requires_confirmation=True)
    return VisualQAIssueDecision(emit=False, requires_confirmation=False)
