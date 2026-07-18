"""LLM structured drafts for visual composition."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from archium.domain.visual.enums import ContinuityRole, DensityLevel, LayoutFamily, VisualContentType


class ArtDirectionDraft(BaseModel):
    concept_name: str
    rationale: str
    visual_tone: list[str] = Field(default_factory=list)
    emotional_keywords: list[str] = Field(default_factory=list)
    palette_strategy: str
    typography_strategy: str
    grid_strategy: str
    image_strategy: str
    drawing_strategy: str
    diagram_strategy: str
    annotation_strategy: str
    cover_strategy: str
    section_strategy: str
    content_strategy: str
    closing_strategy: str
    pacing_strategy: str
    consistency_rules: list[str] = Field(default_factory=list)
    forbidden_styles: list[str] = Field(default_factory=list)


class VisualIntentDraft(BaseModel):
    communication_goal: str
    audience_takeaway: str
    visual_priority: str
    dominant_content_type: VisualContentType
    hero_asset_id: UUID | None = None
    supporting_asset_ids: list[UUID] = Field(default_factory=list)
    hierarchy: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)
    preferred_layout_families: list[LayoutFamily] = Field(default_factory=list)
    composition_strategy: str = ""
    image_treatment: str = ""
    annotation_strategy: str = ""
    background_strategy: str = ""
    density_level: DensityLevel = DensityLevel.BALANCED
    emotional_tone: str = ""
    continuity_role: ContinuityRole = ContinuityRole.EXPLANATION


class LayoutDecisionDraft(BaseModel):
    """LLM may only choose family/variant and content roles — never free coordinates."""

    layout_family: str
    layout_variant: str
    hero_content_ref: str | None = None
    supporting_content_refs: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)
    density_adjustment: str = "balanced"
    split_recommended: bool = False
    split_reason: str | None = None
