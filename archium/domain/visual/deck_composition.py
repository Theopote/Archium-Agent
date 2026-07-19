"""Deck-level visual rhythm and composition planning models."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.enums import DensityLevel, LayoutFamily


class PacingRole(StrEnum):
    OPENING = "opening"
    SETUP = "setup"
    EVIDENCE = "evidence"
    ANALYSIS = "analysis"
    PAUSE = "pause"
    TRANSITION = "transition"
    CLIMAX = "climax"
    DECISION = "decision"
    CLOSING = "closing"


class VisualIntensity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HERO = "hero"


_DENSITY_TO_SCORE: dict[DensityLevel, float] = {
    DensityLevel.SPACIOUS: 0.25,
    DensityLevel.BALANCED: 0.5,
    DensityLevel.COMPACT: 0.75,
}

_INTENSITY_TO_SCORE: dict[VisualIntensity, float] = {
    VisualIntensity.LOW: 0.25,
    VisualIntensity.MEDIUM: 0.5,
    VisualIntensity.HIGH: 0.75,
    VisualIntensity.HERO: 1.0,
}


class SlideCompositionDirective(DomainModel):
    """Per-slide rhythm guidance for layout candidate selection."""

    slide_id: UUID
    slide_index: int = Field(ge=0)

    narrative_role: str = Field(min_length=1)
    pacing_role: PacingRole
    visual_intensity: VisualIntensity
    target_density: DensityLevel

    preferred_layout_families: list[LayoutFamily] = Field(min_length=1)
    forbidden_layout_families: list[LayoutFamily] = Field(default_factory=list)

    hero_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    text_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    drawing_priority: float = Field(default=0.5, ge=0.0, le=1.0)

    transition_mode: str | None = None
    continuity_group: str | None = None

    should_contrast_previous: bool = False
    should_match_previous: bool = False


class SectionCompositionPlan(DomainModel):
    """Chapter-level pacing intent."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    opening_slide_id: UUID | None = None
    climax_slide_id: UUID | None = None
    pacing_notes: str = ""
    target_visual_intensity: VisualIntensity = VisualIntensity.MEDIUM


class DeckCompositionPlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """Deck-wide visual rhythm plan — coordinates, not geometry."""

    presentation_id: UUID
    art_direction_id: UUID

    composition_strategy: str = Field(min_length=1)
    pacing_strategy: str = Field(min_length=1)
    section_strategies: list[SectionCompositionPlan] = Field(default_factory=list)
    slide_directives: list[SlideCompositionDirective] = Field(min_length=1)

    layout_family_distribution: dict[str, int] = Field(default_factory=dict)
    visual_intensity_curve: list[float] = Field(default_factory=list)
    density_curve: list[float] = Field(default_factory=list)

    hero_slide_ids: list[UUID] = Field(default_factory=list)
    section_transition_slide_ids: list[UUID] = Field(default_factory=list)
    climax_slide_ids: list[UUID] = Field(default_factory=list)

    consistency_rules: list[str] = Field(default_factory=list)
    variety_rules: list[str] = Field(default_factory=list)

    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @model_validator(mode="after")
    def _validate_curve_lengths(self) -> DeckCompositionPlan:
        count = len(self.slide_directives)
        if self.visual_intensity_curve and len(self.visual_intensity_curve) != count:
            msg = "visual_intensity_curve length must match slide_directives"
            raise ValueError(msg)
        if self.density_curve and len(self.density_curve) != count:
            msg = "density_curve length must match slide_directives"
            raise ValueError(msg)
        indices = [item.slide_index for item in self.slide_directives]
        if indices != list(range(len(indices))):
            msg = "slide_directives must have contiguous slide_index values from 0"
            raise ValueError(msg)
        return self

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def directive_for_slide(self, slide_id: UUID) -> SlideCompositionDirective | None:
        for directive in self.slide_directives:
            if directive.slide_id == slide_id:
                return directive
        return None

    def primary_family_for_slide(self, slide_id: UUID) -> LayoutFamily | None:
        directive = self.directive_for_slide(slide_id)
        if directive is None or not directive.preferred_layout_families:
            return None
        return directive.preferred_layout_families[0]


def density_to_score(level: DensityLevel) -> float:
    return _DENSITY_TO_SCORE[level]


def intensity_to_score(intensity: VisualIntensity) -> float:
    return _INTENSITY_TO_SCORE[intensity]
