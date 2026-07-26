"""PageDirection — per-slide creative direction without coordinates (v0.3)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel, LayoutFamily


class CompositionBias(StrEnum):
    """Semantic composition bias — generators interpret; no absolute coords."""

    PHOTO_LEFT = "photo_left"
    DIAGRAM_CENTER = "diagram_center"
    CONCLUSION_BAR = "conclusion_bar"
    HERO_FULL = "hero_full"
    DRAWING_DOMINANT = "drawing_dominant"
    TEXT_LEAD = "text_lead"
    EVIDENCE_GRID = "evidence_grid"
    BEFORE_AFTER = "before_after"
    STRATEGY_CARDS = "strategy_cards"


class CopyBudget(DomainModel):
    """Hard caps for page copy — Director enforces one-message discipline."""

    max_title_chars: int = Field(default=36, ge=8, le=120)
    max_message_chars: int = Field(default=100, ge=20, le=400)
    max_key_points: int = Field(default=3, ge=0, le=12)
    max_body_blocks: int = Field(default=2, ge=0, le=8)


class PageDirection(DomainModel):
    """Structured page-level direction for Visual / Brief (no geometry)."""

    single_message: str = Field(min_length=1, max_length=500)
    must_show: list[str] = Field(default_factory=list)
    must_hide: list[str] = Field(default_factory=list)
    composition_bias: list[CompositionBias] = Field(default_factory=list)
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
