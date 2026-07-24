"""Visual concept brief — Vision Engine artifact for a ConceptDirection draft."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel, utc_now
from archium.domain.visual.vision_generation import ArchitectureImageType, VisionStylePreset


class VisualConceptBrief(IdentifiedModel, TimestampedModel):
    """Text-first visual direction for one concept direction (optional pixels)."""

    project_id: UUID
    mission_id: UUID
    concept_direction_id: UUID
    title: str = Field(min_length=1, max_length=200)
    composition_intent: str = ""
    atmosphere: str = ""
    diagram_intent: str = ""
    image_type: ArchitectureImageType = ArchitectureImageType.CONCEPT_SKETCH
    style_preset: VisionStylePreset | str = VisionStylePreset.SOFT_ATMOSPHERE
    subject: str = ""
    elements: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    compiled_prompt: str = ""
    status: str = Field(default="draft", max_length=30)
    asset_id: UUID | None = None
    image_path: str | None = Field(default=None, max_length=2000)
    error_message: str | None = None
    generated_at: datetime | None = None
    extra_json: dict[str, Any] = Field(default_factory=dict)

    def mark_ready(self, *, compiled_prompt: str = "") -> None:
        self.status = "ready"
        if compiled_prompt.strip():
            self.compiled_prompt = compiled_prompt.strip()
        self.touch()

    def mark_imaged(self, *, asset_id: UUID | None, image_path: str | None) -> None:
        self.status = "imaged"
        self.asset_id = asset_id
        self.image_path = image_path
        self.error_message = None
        self.generated_at = utc_now()
        self.touch()

    def mark_failed(self, message: str) -> None:
        self.status = "failed"
        self.error_message = message
        self.touch()
