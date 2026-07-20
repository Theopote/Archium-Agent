"""Scene-level semantic QA codes and report models (WP H §11.2)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.slide_semantic_qa import SlideSemanticFinding


class SceneSemanticCheckCode:
    """Stable identifiers for RenderScene semantic / geometry checks."""

    DRAWING_COVER_MODE_FORBIDDEN = "SEMANTIC.DRAWING_COVER_MODE_FORBIDDEN"
    AI_IMAGE_PRESENTED_AS_REAL_PROJECT = "SEMANTIC.AI_IMAGE_PRESENTED_AS_REAL_PROJECT"
    STOCK_IMAGE_PRESENTED_AS_PROJECT = "SEMANTIC.STOCK_IMAGE_PRESENTED_AS_PROJECT"
    IMAGE_NOT_RENDERED = "SEMANTIC.IMAGE_NOT_RENDERED"
    FONT_TOO_SMALL = "SEMANTIC.FONT_TOO_SMALL"
    TEXT_OVERFLOW = "SEMANTIC.TEXT_OVERFLOW"
    CAPTION_MISSING = "SEMANTIC.CAPTION_MISSING"
    SCENE_PPTX_NODE_MISMATCH = "SEMANTIC.SCENE_PPTX_NODE_MISMATCH"
    FONT_FALLBACK_CHANGED_LAYOUT = "SEMANTIC.FONT_FALLBACK_CHANGED_LAYOUT"

    # Plan aliases → existing slide semantic codes (documented for callers).
    BEFORE_AFTER_UNPAIRED = "SEMANTIC.BEFORE_AFTER_MISMATCH"
    PROJECT_PHOTO_WITHOUT_SOURCE = "SEMANTIC.PROJECT_ASSET_WITHOUT_SOURCE"


class SceneSemanticQA(DomainModel):
    """Aggregated Scene Semantic QA for one or more RenderScenes."""

    presentation_id: UUID | None = None
    slide_id: UUID | None = None
    scene_id: UUID | None = None
    findings: list[SlideSemanticFinding] = Field(default_factory=list)
    analyzer_version: str = Field(default="1.0.0", min_length=1)

    @property
    def issue_count(self) -> int:
        return len(self.findings)
