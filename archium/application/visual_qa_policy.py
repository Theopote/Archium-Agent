"""Confidence policy for heuristic visual QA findings."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual_qa import VisualQACheck

CONFIDENCE_EMIT_FORMAL = 0.85
CONFIDENCE_EMIT_SUSPECTED = 0.60
DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE = 0.75


@dataclass(frozen=True)
class VisualQAIssueDecision:
    """Whether a failed check should become a review issue."""

    emit: bool
    requires_confirmation: bool


def decide_check_issue(check: VisualQACheck) -> VisualQAIssueDecision:
    """Map a failed heuristic check to issue visibility."""
    if check.passed:
        return VisualQAIssueDecision(emit=False, requires_confirmation=False)

    confidence = check.confidence
    if confidence >= CONFIDENCE_EMIT_FORMAL:
        return VisualQAIssueDecision(emit=True, requires_confirmation=False)
    if confidence >= CONFIDENCE_EMIT_SUSPECTED:
        return VisualQAIssueDecision(emit=True, requires_confirmation=True)
    return VisualQAIssueDecision(emit=False, requires_confirmation=False)
