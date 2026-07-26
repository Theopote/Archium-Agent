"""Research → Vision seeds — insight becomes visual references (not pixels).

Visual seat artifact: illustrative seeds only. Never evidence photos.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationMode,
    VisionStylePreset,
)


class ResearchVisualKind(StrEnum):
    """Three default views per research insight."""

    SPATIAL_ANALYSIS = "spatial_analysis"
    CONCEPT_SKETCH = "concept_sketch"
    MODERN_TRANSLATION = "modern_translation"


class ResearchVisualReference(DomainModel):
    """One visual reference derived from a research insight."""

    kind: ResearchVisualKind
    title: str = Field(min_length=1, max_length=200)
    insight: str = ""
    visual_prompt: ConceptVisualPrompt = Field(default_factory=ConceptVisualPrompt)
    image_type: ArchitectureImageType = ArchitectureImageType.CONCEPT_SKETCH
    style: VisionStylePreset | str = VisionStylePreset.COMPETITION_CONCEPT_SKETCH
    purpose: str = ""
    elements: list[str] = Field(default_factory=list)

    def to_image_request(self) -> ImageRequest:
        subject = (self.visual_prompt.image_prompt or self.title).strip()[:500]
        return ImageRequest(
            image_type=self.image_type,
            subject=subject or self.title[:500],
            purpose=(self.purpose or self.insight)[:500] or "research visual reference",
            style=self.style,
            elements=list(self.elements)[:12],
            avoid=[
                "luxury commercial real-estate rendering",
                "photorealistic site survey photo presented as evidence",
            ],
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
            seed_source="research_vision",
        )


class ResearchVisionBundle(DomainModel):
    """Insight → Visual Reference set (typically analysis / sketch / translation)."""

    topic: str = ""
    insight: str = ""
    principle: str = ""
    spatial_translation: str = ""
    source_item_id: UUID | None = None
    seed_source: str = Field(
        default="design_knowledge",
        description="design_knowledge | architecture_case",
    )
    references: list[ResearchVisualReference] = Field(default_factory=list)

    @property
    def has_references(self) -> bool:
        return bool(self.references)

    def primary_visual_prompt(self) -> ConceptVisualPrompt | None:
        """Prefer concept sketch seed for ConceptDirection.visual_prompt."""
        for kind in (
            ResearchVisualKind.CONCEPT_SKETCH,
            ResearchVisualKind.MODERN_TRANSLATION,
            ResearchVisualKind.SPATIAL_ANALYSIS,
        ):
            for ref in self.references:
                if ref.kind == kind and not ref.visual_prompt.is_empty():
                    return ref.visual_prompt
        for ref in self.references:
            if not ref.visual_prompt.is_empty():
                return ref.visual_prompt
        return None

    def to_image_requests(self) -> list[ImageRequest]:
        return [ref.to_image_request() for ref in self.references]

    def to_prompt_block(self) -> str:
        lines = ["【Research→Vision】"]
        if self.topic.strip():
            lines.append(f"主题：{self.topic.strip()}")
        if self.insight.strip():
            lines.append(f"洞察：{self.insight.strip()}")
        if self.principle.strip():
            lines.append(f"原则：{self.principle.strip()}")
        if self.spatial_translation.strip():
            lines.append(f"空间转译：{self.spatial_translation.strip()}")
        for ref in self.references:
            vp = ref.visual_prompt
            lines.append(f"- {ref.kind.value} · {ref.title}")
            if vp.image_prompt.strip():
                lines.append(f"  画面：{vp.image_prompt.strip()[:180]}")
        return "\n".join(lines)
