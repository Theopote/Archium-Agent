"""Pre-layout fixed-canvas content budget for slides."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel

CapacityRecommendedAction = Literal[
    "proceed",
    "adapt_content",
    "split_slide",
    "blocked",
]

# Rule codes for planning warnings / content-adaptation suggestions.
CAPACITY_OVERLOAD_RULE = "CAPACITY.OVERLOAD"
CAPACITY_TIGHT_RULE = "CAPACITY.TIGHT"
CAPACITY_IMPOSSIBLE_RULE = "CAPACITY.IMPOSSIBLE"

# Soft risk ramp: risk 0 at 0.85 ratio, 1.0 at 1.35 ratio.
OVERFLOW_RISK_FLOOR = 0.85
OVERFLOW_RISK_SPAN = 0.5

# Status thresholds (capacity_ratio = required_height / usable_height).
TIGHT_RATIO = 0.85
OVERLOADED_RATIO = 1.0
IMPOSSIBLE_RATIO = 1.5

# Mild overload → shorten; heavy → split.
ADAPT_CONTENT_RATIO = OVERLOADED_RATIO
SPLIT_SLIDE_RATIO = 1.25


class CapacityStatus(StrEnum):
    """Formal pre-layout capacity gate status.

    FITS — content comfortably within fixed canvas.
    TIGHT — may generate candidates, but QA is mandatory.
    OVERLOADED — must adapt content or split; forbid further font shrink.
    IMPOSSIBLE — blocked: even adaptation of current payload cannot fit
    (e.g. drawing min-readable alone exceeds usable area).
    """

    FITS = "fits"
    TIGHT = "tight"
    OVERLOADED = "overloaded"
    IMPOSSIBLE = "impossible"


def capacity_status_for_ratio(
    capacity_ratio: float,
    *,
    drawing_impossible: bool = False,
) -> CapacityStatus:
    if drawing_impossible or capacity_ratio > IMPOSSIBLE_RATIO:
        return CapacityStatus.IMPOSSIBLE
    if capacity_ratio > OVERLOADED_RATIO:
        return CapacityStatus.OVERLOADED
    if capacity_ratio >= TIGHT_RATIO:
        return CapacityStatus.TIGHT
    return CapacityStatus.FITS


class SlideCapacityBudget(DomainModel):
    """Fixed-canvas usable area vs estimated content demand (pre-LayoutPlan).

    ``usable_*`` comes from DesignSystem safe area (page − margins − footer) and
    does not grow with content. ``status`` is the formal gate; ``capacity_ratio > 1``
    (OVERLOADED+) forbids further font shrink.
    """

    usable_width: float = Field(gt=0)
    usable_height: float = Field(gt=0)

    estimated_text_height: float = Field(ge=0)
    image_area_required: float = Field(
        ge=0,
        description="Required image/drawing area in square inches.",
    )
    annotation_area_required: float = Field(
        ge=0,
        description="Required annotation strip area in square inches.",
    )

    # Drawing-specific budgets (photos do not inherit these floors).
    drawing_min_readable_area: float = Field(
        default=0.0,
        ge=0,
        description="Minimum readable drawing viewport area (legend/scale readable).",
    )
    caption_required_height: float = Field(
        default=0.0,
        ge=0,
        description="Required figure caption strip height in inches.",
    )
    legend_required_area: float = Field(
        default=0.0,
        ge=0,
        description="Required legend / north-arrow / scale strip area (sq in).",
    )
    annotation_density: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Expected callout density 0..1; scales annotation strip.",
    )

    capacity_ratio: float = Field(ge=0)
    overflow_risk: float = Field(ge=0, le=1)
    status: CapacityStatus = CapacityStatus.FITS
    recommended_action: CapacityRecommendedAction = "proceed"

    # Measurement audit trail — capacity must use styled real metrics when available.
    used_real_font_metrics: bool = False
    text_language: str = Field(
        default="zh",
        description="Language hint passed into text measurement (zh/en/mixed).",
    )

    @property
    def image_height_budget(self) -> float:
        if self.usable_width <= 0:
            return 0.0
        return self.image_area_required / self.usable_width

    @property
    def annotation_height_budget(self) -> float:
        if self.usable_width <= 0:
            return 0.0
        return self.annotation_area_required / self.usable_width

    @property
    def drawing_min_readable_height(self) -> float:
        if self.usable_width <= 0:
            return 0.0
        return self.drawing_min_readable_area / self.usable_width

    @property
    def legend_height_budget(self) -> float:
        if self.usable_width <= 0:
            return 0.0
        return self.legend_required_area / self.usable_width

    @property
    def is_overloaded(self) -> bool:
        return self.status in {CapacityStatus.OVERLOADED, CapacityStatus.IMPOSSIBLE}

    @property
    def is_blocked(self) -> bool:
        return self.status == CapacityStatus.IMPOSSIBLE

    def blocks_layout_candidates(self, *, block_overloaded: bool = True) -> bool:
        """Whether pre-layout capacity forbids emitting LayoutPlan candidates."""
        if self.status == CapacityStatus.IMPOSSIBLE:
            return True
        return block_overloaded and self.status == CapacityStatus.OVERLOADED

    @property
    def requires_qa(self) -> bool:
        return self.status != CapacityStatus.FITS
