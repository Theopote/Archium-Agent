"""PageDirection — per-slide creative direction without coordinates (v0.3).

Product language: **页主张 (page claim)**. Architects decide *what this page
expresses*; ``composition_bias`` is director-derived layout hint, not the input.
Type name stays ``PageDirection`` to avoid colliding with ``VisualIntent``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel, LayoutFamily


class CompositionBias(StrEnum):
    """Semantic composition bias — generators interpret; no absolute coords.

    Derived by Page Director after the page claim is fixed — not architect input.
    """

    PHOTO_LEFT = "photo_left"
    DIAGRAM_CENTER = "diagram_center"
    CONCLUSION_BAR = "conclusion_bar"
    HERO_FULL = "hero_full"
    DRAWING_DOMINANT = "drawing_dominant"
    TEXT_LEAD = "text_lead"
    EVIDENCE_GRID = "evidence_grid"
    BEFORE_AFTER = "before_after"
    STRATEGY_CARDS = "strategy_cards"


class NarrativeEmotion(StrEnum):
    """Page-level narrative emotion — what the slide *feels like* to argue."""

    PROBLEM = "problem"
    STRATEGY = "strategy"
    CLIMAX = "climax"
    CALM = "calm"
    DECISION = "decision"


class CopyBudget(DomainModel):
    """Hard caps for page copy — Director enforces one-message discipline."""

    max_title_chars: int = Field(default=36, ge=8, le=120)
    max_message_chars: int = Field(default=100, ge=20, le=400)
    max_key_points: int = Field(default=3, ge=0, le=12)
    max_body_blocks: int = Field(default=2, ge=0, le=8)


class PageDirection(DomainModel):
    """Structured page-level direction for Visual / Brief (no geometry).

    Product read order:
    1. ``claim`` / ``single_message`` — 这一页要表达什么
    2. ``narrative_emotion`` — problem / strategy / climax / …
    3. ``evidence_priority`` (``must_show``) — 证据优先级，越前越优先
    4. ``avoid`` (``must_hide``) — 禁止项
    5. ``composition_bias`` — 导演派生的排版偏向（最后一步）
    """

    single_message: str = Field(min_length=1, max_length=500)
    narrative_emotion: NarrativeEmotion = NarrativeEmotion.CALM
    must_show: list[str] = Field(
        default_factory=list,
        description="Ordered evidence priority; earlier items rank higher.",
    )
    must_hide: list[str] = Field(default_factory=list)
    composition_bias: list[CompositionBias] = Field(
        default_factory=list,
        description="Director-derived layout bias — not architect input.",
    )
    copy_budget: CopyBudget = Field(default_factory=CopyBudget)

    preferred_layout_families: list[LayoutFamily] = Field(default_factory=list)
    forbidden_layout_families: list[LayoutFamily] = Field(default_factory=list)
    density_override: DensityLevel | None = None
    # Locked generator variant for Expression Mode (v0.3 Phase 2).
    locked_layout_variant: str | None = None
    expression_mode_id: str | None = None

    situation_rule_id: str | None = None
    evidence: list[str] = Field(default_factory=list)
    source: str = Field(default="rules", min_length=1, max_length=40)

    @property
    def claim(self) -> str:
        """Product alias: 页主张 — what this page must communicate."""
        return self.single_message

    @property
    def evidence_priority(self) -> list[str]:
        """Ordered must-show list (architect evidence order)."""
        return list(self.must_show)

    @property
    def avoid(self) -> list[str]:
        """Product alias for must_hide."""
        return list(self.must_hide)

    def as_page_claim(self) -> dict[str, Any]:
        """Investor/designer card — claim first; layout bias marked as derived."""
        return {
            "claim": self.claim,
            "emotion": self.narrative_emotion.value,
            "evidence_priority": self.evidence_priority,
            "avoid": self.avoid,
            "copy_budget": self.copy_budget.model_dump(mode="json"),
            "derived_composition_bias": [item.value for item in self.composition_bias],
            "preferred_layout_families": [
                item.value for item in self.preferred_layout_families
            ],
            "situation_rule_id": self.situation_rule_id,
            "expression_mode_id": self.expression_mode_id,
            "source": self.source,
        }
