"""Layout validation report models and Layout Quality Score."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, computed_field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.severity import layout_fails_validation


class LayoutValidationIssue(DomainModel):
    """A single layout validation finding with a stable rule code."""

    rule_code: str = Field(min_length=1)
    severity: LayoutIssueSeverity
    element_ids: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    suggestion: str | None = None
    auto_repairable: bool = False


class LayoutScore(DomainModel):
    """Layout Quality Score — structural / geometric / rule-based only.

    Round 1 measures whether a LayoutPlan is *mechanically sound*:
    validity, readability, hierarchy, alignment, whitespace, asset usage,
    consistency.

    This is **not** a Visual Quality Score. It does **not** judge:
    image–message fit, architectural presentation presence, color harmony,
    multi-page rhythm, case-image consistency, or “non-overlapping but
    mechanical” composition. Those require a later screenshot-based
    Visual Critic.
    """

    score_kind: Literal["layout_quality"] = "layout_quality"
    validity_score: float = Field(ge=0.0, le=1.0)
    readability_score: float = Field(ge=0.0, le=1.0)
    hierarchy_score: float = Field(ge=0.0, le=1.0)
    alignment_score: float = Field(ge=0.0, le=1.0)
    whitespace_score: float = Field(ge=0.0, le=1.0)
    asset_usage_score: float = Field(ge=0.0, le=1.0)
    consistency_score: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)


# Prefer this name in new code / docs; LayoutScore kept for serialization stability.
LayoutQualityScore = LayoutScore


class LayoutValidationReport(DomainModel):
    """Aggregated validation result for a LayoutPlan.

    ``score`` / ``layout_score`` are **Layout Quality** metrics (geometry + rules),
    not full visual quality.
    """

    issues: list[LayoutValidationIssue] = Field(default_factory=list)
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Layout Quality Score total (0–1). Not Visual Quality.",
    )
    layout_score: LayoutScore | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def valid(self) -> bool:
        return not any(layout_fails_validation(issue.severity) for issue in self.issues)

    @property
    def layout_quality_score(self) -> float:
        """Alias clarifying that ``score`` is Layout Quality, not Visual Quality."""
        return self.score

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
LAYOUT_MISSING_ASSET_REFERENCE = "LAYOUT.MISSING_ASSET_REFERENCE"
LAYOUT_UNRESOLVED_ASSET_PATH = "LAYOUT.UNRESOLVED_ASSET_PATH"
LAYOUT_HERO_ASSET_MISSING = "LAYOUT.HERO_ASSET_MISSING"
LAYOUT_TECHNICAL_DRAWING_MISSING = "LAYOUT.TECHNICAL_DRAWING_MISSING"
LAYOUT_UNSUPPORTED_IMAGE_FORMAT = "LAYOUT.UNSUPPORTED_IMAGE_FORMAT"
