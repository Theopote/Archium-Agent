"""Decoration recipes — dividers, axes, section indices (Visual Decoration Layer)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class DividerKind(StrEnum):
    HORIZONTAL_RULE = "horizontal_rule"
    VERTICAL_AXIS = "vertical_axis"
    SECTION_INDEX = "section_index"
    DOTTED = "dotted"


class DecorationId(StrEnum):
    AXIS_LINE = "axis_line"
    THIN_LINE = "thin_line"
    SECTION_LABEL_01 = "section_label_01"
    SECTION_LABEL = "section_label"


class CardStyle(StrEnum):
    """Restrained architectural cards — not SaaS product cards."""

    TECHNICAL = "technical_card"
    CONCEPT = "concept_card"
    METRIC = "metric_card"
    TIMELINE = "timeline_card"
    EVIDENCE = "evidence_card"
    NONE = "none"


class DecorationRecipe(DomainModel):
    """Which decoration primitives to materialize on the page."""

    decorations: list[DecorationId] = Field(default_factory=list, max_length=8)
    divider_kind: DividerKind | None = None
    section_index: str | None = Field(default=None, max_length=12)
    section_label: str | None = Field(default=None, max_length=40)
    card_style: CardStyle = CardStyle.NONE

    def as_dict(self) -> dict[str, object]:
        return {
            "decorations": [item.value for item in self.decorations],
            "divider_kind": self.divider_kind.value if self.divider_kind else None,
            "section_index": self.section_index,
            "section_label": self.section_label,
            "card_style": self.card_style.value,
        }
