"""Pre-layout fixed-canvas content budget for slides."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel

CapacityRecommendedAction = Literal["proceed", "adapt_content", "split_slide"]

# Rule code for content-adaptation suggestions triggered by capacity gate.
CAPACITY_OVERLOAD_RULE = "CAPACITY.OVERLOAD"

# Soft risk ramp: risk 0 at 0.85 ratio, 1.0 at 1.35 ratio.
OVERFLOW_RISK_FLOOR = 0.85
OVERFLOW_RISK_SPAN = 0.5

# Mild overload → shorten; heavy → split.
ADAPT_CONTENT_RATIO = 1.0
SPLIT_SLIDE_RATIO = 1.25


class SlideCapacityBudget(DomainModel):
    """Fixed-canvas usable area vs estimated content demand (pre-LayoutPlan).

    ``usable_*`` comes from DesignSystem safe area (page − margins − footer) and
    does not grow with content. ``capacity_ratio > 1.0`` means content does not
    fit without adaptation or split — further font shrink is forbidden.
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

    capacity_ratio: float = Field(ge=0)
    overflow_risk: float = Field(ge=0, le=1)
    recommended_action: CapacityRecommendedAction = "proceed"

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
    def is_overloaded(self) -> bool:
        return self.capacity_ratio > ADAPT_CONTENT_RATIO
