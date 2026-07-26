"""VisualBudget — decoration / accent caps so rhetoric does not become Canva clutter."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class VisualBudget(DomainModel):
    """Hard caps for visual rhetoric density (parallel to CopyBudget)."""

    hero_ratio: float = Field(
        default=0.55,
        ge=0.2,
        le=0.9,
        description="Target share of page for primary visual / hero.",
    )
    accent_elements: int = Field(default=3, ge=0, le=12)
    decorative_lines: int = Field(default=2, ge=0, le=8)
    icons: int = Field(default=2, ge=0, le=8)
    color_blocks: int = Field(default=1, ge=0, le=6)

    def as_dict(self) -> dict[str, object]:
        return {
            "hero_ratio": self.hero_ratio,
            "accent_elements": self.accent_elements,
            "decorative_lines": self.decorative_lines,
            "icons": self.icons,
            "color_blocks": self.color_blocks,
        }


# Presets by narrative emotion / page kind (Director picks; concept may tighten).
BUDGET_PROBLEM = VisualBudget(
    hero_ratio=0.5,
    accent_elements=3,
    decorative_lines=6,
    icons=2,
    color_blocks=1,
)
BUDGET_STRATEGY = VisualBudget(
    hero_ratio=0.4,
    accent_elements=4,
    decorative_lines=2,
    icons=3,
    color_blocks=1,
)
BUDGET_CLIMAX = VisualBudget(
    hero_ratio=0.7,
    accent_elements=2,
    decorative_lines=1,
    icons=0,
    color_blocks=0,
)
BUDGET_CALM = VisualBudget(
    hero_ratio=0.55,
    accent_elements=2,
    decorative_lines=1,
    icons=1,
    color_blocks=1,
)
BUDGET_DECISION = VisualBudget(
    hero_ratio=0.35,
    accent_elements=3,
    decorative_lines=1,
    icons=2,
    color_blocks=1,
)
