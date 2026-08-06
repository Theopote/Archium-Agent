"""ArtDirection — presentation-level visual language (not per-slide coordinates)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus


class ArtDirection(IdentifiedModel, VersionedModel, TimestampedModel):
    """Defines the visual language for an entire deliverable."""

    project_id: UUID
    deliverable_id: str | None = None
    presentation_id: UUID | None = None
    concept_name: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1)
    visual_tone: list[str] = Field(default_factory=list)
    emotional_keywords: list[str] = Field(default_factory=list)

    # Structured strategies (v0.4+) — Union allows gradual migration
    palette_strategy: Any = Field(
        description="Color palette strategy: str (legacy) or PaletteStrategy (structured)",
    )
    typography_strategy: Any = Field(
        description="Typography strategy: str (legacy) or TypographyStrategy (structured)",
    )
    grid_strategy: Any = Field(
        description="Grid and spacing strategy: str (legacy) or GridStrategy (structured)",
    )

    # Legacy string strategies (maintained for backward compatibility)
    image_strategy: str = Field(min_length=1)
    drawing_strategy: str = Field(min_length=1)
    diagram_strategy: str = Field(min_length=1)
    annotation_strategy: str = Field(min_length=1)
    cover_strategy: str = Field(min_length=1)
    section_strategy: str = Field(min_length=1)
    content_strategy: str = Field(min_length=1)
    closing_strategy: str = Field(min_length=1)
    pacing_strategy: str = Field(min_length=1)
    consistency_rules: list[str] = Field(default_factory=list)
    forbidden_styles: list[str] = Field(default_factory=list)
    design_system_id: UUID | None = None
    # Architecture Style Preset id (e.g. architecture_minimal). Applies measurable
    # DesignSystem overlays; distinct from Vision image-generation style presets.
    style_preset_id: str | None = None
    # Bound TemplateUsageBrief snapshot — survives template re-induction.
    template_usage_brief_id: UUID | None = None
    template_usage_brief_version: int | None = Field(default=None, ge=1)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @field_validator("palette_strategy", mode="before")
    @classmethod
    def _coerce_palette_strategy(cls, value: Any) -> Any:
        """Accept dict and convert to PaletteStrategy, or pass through str/object."""
        if isinstance(value, dict):
            from archium.domain.visual.art_direction_strategies import PaletteStrategy
            return PaletteStrategy.model_validate(value)
        return value

    @field_validator("typography_strategy", mode="before")
    @classmethod
    def _coerce_typography_strategy(cls, value: Any) -> Any:
        """Accept dict and convert to TypographyStrategy, or pass through str/object."""
        if isinstance(value, dict):
            from archium.domain.visual.art_direction_strategies import TypographyStrategy
            return TypographyStrategy.model_validate(value)
        return value

    @field_validator("grid_strategy", mode="before")
    @classmethod
    def _coerce_grid_strategy(cls, value: Any) -> Any:
        """Accept dict and convert to GridStrategy, or pass through str/object."""
        if isinstance(value, dict):
            from archium.domain.visual.art_direction_strategies import GridStrategy
            return GridStrategy.model_validate(value)
        return value

    def has_structured_palette(self) -> bool:
        """Check if palette_strategy is structured (not string)."""
        return not isinstance(self.palette_strategy, str)

    def has_structured_typography(self) -> bool:
        """Check if typography_strategy is structured (not string)."""
        return not isinstance(self.typography_strategy, str)

    def has_structured_grid(self) -> bool:
        """Check if grid_strategy is structured (not string)."""
        return not isinstance(self.grid_strategy, str)

    def get_palette_strategy(self) -> Any:
        """Get palette strategy, converting from string if needed."""
        if isinstance(self.palette_strategy, str):
            from archium.domain.visual.art_direction_strategies import palette_strategy_from_string
            return palette_strategy_from_string(self.palette_strategy)
        return self.palette_strategy

    def get_typography_strategy(self) -> Any:
        """Get typography strategy, converting from string if needed."""
        if isinstance(self.typography_strategy, str):
            from archium.domain.visual.art_direction_strategies import typography_strategy_from_string
            return typography_strategy_from_string(self.typography_strategy)
        return self.typography_strategy

    def get_grid_strategy(self) -> Any:
        """Get grid strategy, converting from string if needed."""
        if isinstance(self.grid_strategy, str):
            from archium.domain.visual.art_direction_strategies import grid_strategy_from_string
            return grid_strategy_from_string(self.grid_strategy)
        return self.grid_strategy

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()
