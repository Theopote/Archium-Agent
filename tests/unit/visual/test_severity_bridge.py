"""DOM-004: canonical gate severity bridges."""

from __future__ import annotations

from archium.domain.enums import ReviewSeverity, ValidationSeverity
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.severity import (
    GateSeverity,
    gate_to_review,
    is_gate_blocker,
    layout_fails_validation,
    layout_is_gate_blocker,
    layout_to_gate,
    layout_to_review,
    review_to_gate,
    validation_to_gate,
)


def test_gate_severity_alias_is_issue_severity() -> None:
    assert GateSeverity is IssueSeverity


def test_layout_to_gate_mapping() -> None:
    assert layout_to_gate(LayoutIssueSeverity.CRITICAL) == IssueSeverity.BLOCKER
    assert layout_to_gate(LayoutIssueSeverity.ERROR) == IssueSeverity.MAJOR
    assert layout_to_gate(LayoutIssueSeverity.WARNING) == IssueSeverity.MINOR
    assert layout_to_gate(LayoutIssueSeverity.INFO) == IssueSeverity.MINOR


def test_layout_gate_blocker_is_critical_only() -> None:
    assert layout_is_gate_blocker(LayoutIssueSeverity.CRITICAL) is True
    assert layout_is_gate_blocker(LayoutIssueSeverity.ERROR) is False
    assert layout_fails_validation(LayoutIssueSeverity.ERROR) is True


def test_review_round_trip_through_gate() -> None:
    assert review_to_gate(ReviewSeverity.CRITICAL) == IssueSeverity.BLOCKER
    assert review_to_gate(ReviewSeverity.HIGH) == IssueSeverity.MAJOR
    assert gate_to_review(IssueSeverity.BLOCKER) == ReviewSeverity.CRITICAL
    assert gate_to_review(IssueSeverity.MAJOR) == ReviewSeverity.HIGH
    assert is_gate_blocker(review_to_gate(ReviewSeverity.CRITICAL)) is True


def test_layout_to_review_preserves_info_as_suggestion() -> None:
    assert layout_to_review(LayoutIssueSeverity.ERROR) == ReviewSeverity.HIGH
    assert layout_to_review(LayoutIssueSeverity.INFO) == ReviewSeverity.SUGGESTION


def test_validation_to_gate_mission_scope() -> None:
    assert validation_to_gate(ValidationSeverity.FATAL) == IssueSeverity.BLOCKER
    assert validation_to_gate(ValidationSeverity.ERROR) == IssueSeverity.MAJOR
