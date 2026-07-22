"""Structured LLM schemas for slide recovery VLM region analysis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SlideRecoveryRegionDraft(BaseModel):
    region_type: str = Field(
        description="text | image | drawing | table | chart | line | shape | background"
    )
    bbox_x: float = Field(ge=0.0, le=1.0)
    bbox_y: float = Field(ge=0.0, le=1.0)
    bbox_width: float = Field(gt=0.0, le=1.0)
    bbox_height: float = Field(gt=0.0, le=1.0)
    semantic_role: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    recovered_text: str = ""
    keep_whole_drawing: bool = False
    bitmap_fallback: bool = False


class SlideRecoveryPageAnalysisDraft(BaseModel):
    page_kind: str = Field(
        description="title | image_text | table | photo | drawing_dominant"
    )
    regions: list[SlideRecoveryRegionDraft] = Field(default_factory=list)
    summary: str = ""
