"""Structured LLM schemas for asset vision captioning."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssetVisionCaptionDraft(BaseModel):
    drawing_type: str = Field(
        description="site_plan | floor_plan | section | elevation | diagram | photo | unknown"
    )
    summary: str = Field(min_length=1, description="Dense Chinese description for retrieval")
    spatial_elements: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    metrics_visible: list[str] = Field(default_factory=list)
    scale_or_north: str | None = None
