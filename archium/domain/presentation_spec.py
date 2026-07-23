"""Renderer-agnostic presentation specification for editable PPTX export."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.plan_overlay import PlanOverlayMetadata
from archium.domain.visual.structured_payload import (
    ChartDataPayload,
    ChartSeriesData,
    TableDataPayload,
)

# DOM-012: Spec chart/table payloads share the canonical VO with Layout/Scene.
SpecChartSeries = ChartSeriesData
SpecChart = ChartDataPayload
SpecTable = TableDataPayload


class SpecImagePlacement(DomainModel):
    """Optional image slot on a slide."""

    description: str
    asset_path: str | None = None
    generated: bool = False
    web_sourced: bool = False
    attribution: str | None = None
    source_url: str | None = None
    x: float = 5.0
    y: float = 1.5
    w: float = 4.0
    h: float = 4.0


class SpecColumn(DomainModel):
    """One column in a comparison layout."""

    label: str = Field(min_length=1)
    message: str | None = None
    bullets: list[str] = Field(default_factory=list)


class SpecTimelineItem(DomainModel):
    """One milestone on a timeline layout."""

    label: str = Field(min_length=1)
    text: str = Field(min_length=1)


class SpecMetric(DomainModel):
    """One metric cell on a data layout."""

    label: str = Field(min_length=1)
    value: str = Field(min_length=1)


class SpecSlide(DomainModel):
    """One slide in a PresentationSpec."""

    order: int = Field(ge=0)
    layout: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = None
    message: str | None = None
    bullets: list[str] = Field(default_factory=list)
    speaker_notes: str | None = None
    images: list[SpecImagePlacement] = Field(default_factory=list)
    columns: list[SpecColumn] = Field(default_factory=list)
    timeline_items: list[SpecTimelineItem] = Field(default_factory=list)
    metrics: list[SpecMetric] = Field(default_factory=list)
    chart: SpecChart | None = None
    table: SpecTable | None = None
    plan_overlays: PlanOverlayMetadata | None = None


class PresentationSpec(DomainModel):
    """Intermediate export format consumed by PptxGenJS templates."""

    presentation_id: str
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    theme: str = "architecture-board"
    language: str = "zh-CN"
    slides: list[SpecSlide] = Field(default_factory=list)
