"""Canonical severity vocabulary and bridges (DOM-004).

**Gate authority:** ``IssueSeverity`` (blocker / major / minor) is the only
severity formal export readiness and quality catalogs reason about.

Other enums remain for their local pipelines and must convert through this
module when crossing into gates, review persistence, or page-quality status:

- ``LayoutIssueSeverity`` — layout validation / deck QA findings
- ``ReviewSeverity`` — persisted ``ReviewIssue`` rows
- ``ValidationSeverity`` — mission planning only (not export)

Layout validation hard-fail (``CRITICAL``|``ERROR``) is a layout-pipeline
concept; only ``CRITICAL`` maps to gate ``BLOCKER``. ``ERROR`` maps to
``MAJOR`` (needs review / may soft-block via rule lists).
"""

from __future__ import annotations

from archium.domain.enums import ReviewSeverity, ValidationSeverity
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.page_quality import IssueSeverity

# Public alias: prefer this name at gate / readiness call sites.
GateSeverity = IssueSeverity

LAYOUT_TO_GATE: dict[LayoutIssueSeverity, IssueSeverity] = {
    LayoutIssueSeverity.CRITICAL: IssueSeverity.BLOCKER,
    LayoutIssueSeverity.ERROR: IssueSeverity.MAJOR,
    LayoutIssueSeverity.WARNING: IssueSeverity.MINOR,
    LayoutIssueSeverity.INFO: IssueSeverity.MINOR,
}

GATE_TO_REVIEW: dict[IssueSeverity, ReviewSeverity] = {
    IssueSeverity.BLOCKER: ReviewSeverity.CRITICAL,
    IssueSeverity.MAJOR: ReviewSeverity.HIGH,
    IssueSeverity.MINOR: ReviewSeverity.MEDIUM,
}

REVIEW_TO_GATE: dict[ReviewSeverity, IssueSeverity] = {
    ReviewSeverity.CRITICAL: IssueSeverity.BLOCKER,
    ReviewSeverity.HIGH: IssueSeverity.MAJOR,
    ReviewSeverity.MEDIUM: IssueSeverity.MINOR,
    ReviewSeverity.SUGGESTION: IssueSeverity.MINOR,
}

# Review emission keeps INFO as suggestion (softer than MEDIUM).
LAYOUT_TO_REVIEW: dict[LayoutIssueSeverity, ReviewSeverity] = {
    LayoutIssueSeverity.CRITICAL: ReviewSeverity.CRITICAL,
    LayoutIssueSeverity.ERROR: ReviewSeverity.HIGH,
    LayoutIssueSeverity.WARNING: ReviewSeverity.MEDIUM,
    LayoutIssueSeverity.INFO: ReviewSeverity.SUGGESTION,
}

VALIDATION_TO_GATE: dict[ValidationSeverity, IssueSeverity] = {
    ValidationSeverity.FATAL: IssueSeverity.BLOCKER,
    ValidationSeverity.ERROR: IssueSeverity.MAJOR,
    ValidationSeverity.WARNING: IssueSeverity.MINOR,
    ValidationSeverity.SUGGESTION: IssueSeverity.MINOR,
}

_GATE_RANK: dict[IssueSeverity, int] = {
    IssueSeverity.MINOR: 0,
    IssueSeverity.MAJOR: 1,
    IssueSeverity.BLOCKER: 2,
}

_REVIEW_RANK: dict[ReviewSeverity, int] = {
    ReviewSeverity.SUGGESTION: 0,
    ReviewSeverity.MEDIUM: 1,
    ReviewSeverity.HIGH: 2,
    ReviewSeverity.CRITICAL: 3,
}


def layout_to_gate(severity: LayoutIssueSeverity) -> IssueSeverity:
    return LAYOUT_TO_GATE[severity]


def gate_to_review(severity: IssueSeverity) -> ReviewSeverity:
    return GATE_TO_REVIEW[severity]


def review_to_gate(severity: ReviewSeverity) -> IssueSeverity:
    return REVIEW_TO_GATE[severity]


def layout_to_review(severity: LayoutIssueSeverity) -> ReviewSeverity:
    return LAYOUT_TO_REVIEW[severity]


def validation_to_gate(severity: ValidationSeverity) -> IssueSeverity:
    """Mission-planning severity → gate vocabulary (documentation / future use)."""
    return VALIDATION_TO_GATE[severity]


def gate_rank(severity: IssueSeverity) -> int:
    return _GATE_RANK[severity]


def review_rank(severity: ReviewSeverity) -> int:
    return _REVIEW_RANK[severity]


def is_gate_blocker(severity: IssueSeverity) -> bool:
    return severity == IssueSeverity.BLOCKER


def layout_is_gate_blocker(severity: LayoutIssueSeverity) -> bool:
    """True when layout severity maps to export/quality BLOCKER (CRITICAL only)."""
    return is_gate_blocker(layout_to_gate(severity))


def layout_fails_validation(severity: LayoutIssueSeverity) -> bool:
    """Layout-pipeline hard fail used by LayoutValidationReport (CRITICAL|ERROR)."""
    return severity in {LayoutIssueSeverity.CRITICAL, LayoutIssueSeverity.ERROR}


def max_gate_severity(*severities: IssueSeverity) -> IssueSeverity | None:
    if not severities:
        return None
    return max(severities, key=gate_rank)


def coerce_review_severity_label(raw: str) -> ReviewSeverity:
    """Map free-text finding severity labels onto ReviewSeverity."""
    key = raw.strip().lower()
    try:
        return ReviewSeverity(key)
    except ValueError:
        aliases = {
            "blocker": ReviewSeverity.CRITICAL,
            "error": ReviewSeverity.HIGH,
            "warning": ReviewSeverity.MEDIUM,
            "info": ReviewSeverity.SUGGESTION,
            "major": ReviewSeverity.HIGH,
            "minor": ReviewSeverity.MEDIUM,
        }
        return aliases.get(key, ReviewSeverity.MEDIUM)
