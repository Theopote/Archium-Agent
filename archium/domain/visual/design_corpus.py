"""Design Corpus — annotated architectural presentation pages (no training).

Structured labels for Visual Rhetoric matching. Images optional; v1 seeds are
metadata-only so CI stays light.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class DesignCorpusPage(DomainModel):
    """One labeled page — fields align with Grammar §7."""

    id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=64)
    page_type: str = Field(min_length=1, max_length=40)
    visual_pattern: str = Field(min_length=1, max_length=64)
    image_ratio: float = Field(default=0.55, ge=0.0, le=1.0)
    text_density: float = Field(default=0.2, ge=0.0, le=1.0)
    dominant_element: str = Field(default="drawing", max_length=40)
    style: str = Field(default="minimal_architecture", max_length=64)
    metaphor: str | None = Field(default=None, max_length=64)
    formula_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=120)
    claim: str | None = Field(default=None, max_length=280)
    image_path: str | None = Field(default=None, max_length=260)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "page_type": self.page_type,
            "visual_pattern": self.visual_pattern,
            "image_ratio": self.image_ratio,
            "text_density": self.text_density,
            "dominant_element": self.dominant_element,
            "style": self.style,
            "metaphor": self.metaphor,
            "formula_id": self.formula_id,
            "title": self.title,
            "claim": self.claim,
            "image_path": self.image_path,
        }
