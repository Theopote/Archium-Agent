"""Icon usage policy — when and how many icons may appear on a page."""

from __future__ import annotations

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutFamily
from pydantic import Field


class IconUsagePolicy(DomainModel):
    """Product rules that prevent every card from becoming an infographic sticker.

    Registry + Matcher select *which* icon; this policy decides *whether* and
    *how many* icons may be placed.
    """

    max_icons_per_page: int = Field(default=4, ge=0, le=12)
    min_match_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    allow_decorative: bool = False
    allow_on_drawing_pages: bool = False
    remove_when_capacity_overloaded: bool = True
    remove_when_density_high: bool = True

    # Families where semantic icons are welcome (process / metrics).
    allowed_layout_families: list[str] = Field(
        default_factory=lambda: [
            LayoutFamily.PROCESS_NARRATIVE.value,
            LayoutFamily.METRIC_DASHBOARD.value,
            LayoutFamily.STRATEGY_CARDS.value,
            LayoutFamily.HERO.value,
        ]
    )
    # Families where icons are banned (evidence / drawings stay clean).
    forbidden_layout_families: list[str] = Field(
        default_factory=lambda: [
            LayoutFamily.DRAWING_FOCUS.value,
            LayoutFamily.EVIDENCE_BOARD.value,
            LayoutFamily.ANALYTICAL_DIAGRAM.value,
        ]
    )

    max_icons_metric_dashboard: int = Field(default=4, ge=0, le=8)
    max_icons_process_narrative: int = Field(default=5, ge=0, le=8)


def default_icon_usage_policy() -> IconUsagePolicy:
    return IconUsagePolicy()
