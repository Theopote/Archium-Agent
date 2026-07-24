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

    def to_prompt_block(self) -> str:
        """Compact text for Brief / Storyline / Outline generation context."""
        style = (
            self.style_preset.value
            if hasattr(self.style_preset, "value")
            else str(self.style_preset)
        )
        sections: list[str] = [
            f"视觉简报：{self.title}",
            f"图类：{self.image_type.value} · 风格：{style}",
        ]
        if self.subject.strip():
            sections.append(f"主体：{self.subject.strip()}")
        if self.composition_intent.strip():
            sections.append(f"构图意图：{self.composition_intent.strip()}")
        if self.atmosphere.strip():
            sections.append(f"氛围：{self.atmosphere.strip()}")
        if self.diagram_intent.strip():
            sections.append(f"图示意图：{self.diagram_intent.strip()}")
        if self.elements:
            sections.append(
                "要素：\n" + "\n".join(f"- {item}" for item in self.elements if item.strip())
            )
        if self.avoid:
            sections.append(
                "避免：\n" + "\n".join(f"- {item}" for item in self.avoid if item.strip())
            )
        if self.compiled_prompt.strip():
            sections.append(f"编译提示（节选）：{self.compiled_prompt.strip()[:400]}")
        if self.image_path:
            sections.append(f"示意路径：{self.image_path}（illustrative only，非现场证据）")
        return "\n".join(sections)
