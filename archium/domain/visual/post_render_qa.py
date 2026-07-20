"""Post-render screenshot QA codes and report models (WP H §11.3)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.slide_semantic_qa import SlideSemanticFinding


class PostRenderCheckCode:
    """Stable identifiers for rendered page screenshot checks."""

    BLANK_PAGE = "POST_RENDER.BLANK_PAGE"
    BLACK_BLOCK = "POST_RENDER.BLACK_BLOCK"
    IMAGE_NOT_LOADED = "POST_RENDER.IMAGE_NOT_LOADED"
    DUPLICATE_PAGE = "POST_RENDER.DUPLICATE_PAGE"
    ALL_PAGES_IDENTICAL = "POST_RENDER.ALL_PAGES_IDENTICAL"
    DRAWING_BLUR = "POST_RENDER.DRAWING_BLUR"
    SEVERE_STRETCH = "POST_RENDER.SEVERE_STRETCH"
    PNG_PPTX_DIFF = "POST_RENDER.PNG_PPTX_DIFF"


class PostRenderQA(DomainModel):
    """Aggregated post-render screenshot QA for a presentation."""

    presentation_id: UUID | None = None
    findings: list[SlideSemanticFinding] = Field(default_factory=list)
    checked_page_count: int = Field(default=0, ge=0)
    skipped: bool = False
    skip_reason: str | None = None
    analyzer_version: str = Field(default="1.0.0", min_length=1)

    @property
    def issue_count(self) -> int:
        return len(self.findings)
