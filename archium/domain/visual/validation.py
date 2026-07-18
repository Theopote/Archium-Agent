"""Layout validation report models and scoring."""

from __future__ import annotations

from pydantic import Field, computed_field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutIssueSeverity


class LayoutValidationIssue(DomainModel):
    """A single layout validation finding with a stable rule code."""

    rule_code: str = Field(min_length=1)
    severity: LayoutIssueSeverity
    element_ids: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    suggestion: str | None = None
    auto_repairable: bool = False


class LayoutScore(DomainModel):
    """Rule-based layout quality score (no vision model required)."""

    validity_score: float = Field(ge=0.0, le=1.0)
    readability_score: float = Field(ge=0.0, le=1.0)
    hierarchy_score: float = Field(ge=0.0, le=1.0)
    alignment_score: float = Field(ge=0.0, le=1.0)
    whitespace_score: float = Field(ge=0.0, le=1.0)
    asset_usage_score: float = Field(ge=0.0, le=1.0)
    consistency_score: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)


class LayoutValidationReport(DomainModel):
    """Aggregated validation result for a LayoutPlan."""

    issues: list[LayoutValidationIssue] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    layout_score: LayoutScore | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def valid(self) -> bool:
        return not any(
            issue.severity in {LayoutIssueSeverity.CRITICAL, LayoutIssueSeverity.ERROR}
            for issue in self.issues
        )

    def issues_for(self, rule_code: str) -> list[LayoutValidationIssue]:
        return [issue for issue in self.issues if issue.rule_code == rule_code]

    def has_critical(self) -> bool:
        return any(issue.severity == LayoutIssueSeverity.CRITICAL for issue in self.issues)


# Stable rule codes (first edition).
LAYOUT_ELEMENT_OUTSIDE_PAGE = "LAYOUT.ELEMENT_OUTSIDE_PAGE"
LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA = "LAYOUT.ELEMENT_OUTSIDE_SAFE_AREA"
LAYOUT_ELEMENT_OVERLAP = "LAYOUT.ELEMENT_OVERLAP"
LAYOUT_INVALID_SIZE = "LAYOUT.INVALID_SIZE"
LAYOUT_MISSING_TITLE = "LAYOUT.MISSING_TITLE"
LAYOUT_MISSING_SOURCE = "LAYOUT.MISSING_SOURCE"
LAYOUT_TEXT_OVERFLOW = "LAYOUT.TEXT_OVERFLOW"
LAYOUT_FONT_TOO_SMALL = "LAYOUT.FONT_TOO_SMALL"
LAYOUT_IMAGE_DISTORTION = "LAYOUT.IMAGE_DISTORTION"
LAYOUT_DRAWING_CROPPED = "LAYOUT.DRAWING_CROPPED"
LAYOUT_HERO_NOT_DOMINANT = "LAYOUT.HERO_NOT_DOMINANT"
LAYOUT_EXCESSIVE_DENSITY = "LAYOUT.EXCESSIVE_DENSITY"
LAYOUT_INSUFFICIENT_WHITESPACE = "LAYOUT.INSUFFICIENT_WHITESPACE"
LAYOUT_INCONSISTENT_ALIGNMENT = "LAYOUT.INCONSISTENT_ALIGNMENT"
