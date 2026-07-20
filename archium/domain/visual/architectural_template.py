"""Architectural template domain models for Template Studio."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.visual.render_scene import FontAsset


class TemplateStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class TemplatePageType(StrEnum):
    COVER = "cover"
    SECTION = "section"
    AGENDA = "agenda"
    TEXT_ARGUMENT = "text_argument"
    DRAWING_FOCUS = "drawing_focus"
    PHOTO_GRID = "photo_grid"
    BEFORE_AFTER = "before_after"
    CASE_COMPARISON = "case_comparison"
    METRIC = "metric"
    TIMELINE = "timeline"
    PROCESS = "process"
    CLOSING = "closing"
    UNKNOWN = "unknown"


class TemplateSlotRole(StrEnum):
    TITLE = "title"
    SUBTITLE = "subtitle"
    BODY = "body"
    HERO_IMAGE = "hero_image"
    SUPPORTING_IMAGE = "supporting_image"
    DRAWING = "drawing"
    METRIC = "metric"
    CAPTION = "caption"
    SOURCE = "source"
    CHART = "chart"
    TABLE = "table"
    DECORATION = "decoration"


class PowerPointMasterMetadata(DomainModel):
    """Lightweight metadata extracted from a PowerPoint deck."""

    slide_count: int = Field(ge=0, default=0)
    slide_width_emu: int = Field(ge=0, default=0)
    slide_height_emu: int = Field(ge=0, default=0)
    has_slide_master: bool = False
    master_count: int = Field(ge=0, default=0)
    layout_count: int = Field(ge=0, default=0)
    encrypted_or_unreadable: bool = False
    notes: str = ""


class TemplateSlot(DomainModel):
    """A content region on a template page (geometry in inches)."""

    id: str = Field(min_length=1)
    role: TemplateSlotRole = TemplateSlotRole.BODY
    required: bool = False
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    accepted_node_types: list[str] = Field(default_factory=lambda: ["text", "image"])
    accepted_asset_origins: list[str] = Field(default_factory=list)
    accepted_drawing_types: list[str] = Field(default_factory=list)
    min_content_count: int = Field(default=1, ge=0)
    max_content_count: int = Field(default=1, ge=1)
    crop_policy: str = "none"
    overflow_policy: str = "shrink"
    architectural_constraints: list[str] = Field(default_factory=list)
    label: str = ""
    source_shape_name: str = ""
    auto_detected: bool = True


class ArchitecturalTemplateLayout(DomainModel):
    """One page layout within an architectural template."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1)
    description: str = ""
    page_index: int = Field(ge=0)
    page_type: TemplatePageType = TemplatePageType.UNKNOWN
    suitable_slide_types: list[str] = Field(default_factory=list)
    suitable_content_types: list[str] = Field(default_factory=list)
    architectural_roles: list[str] = Field(default_factory=list)
    slots: list[TemplateSlot] = Field(default_factory=list)
    supports_drawing: bool = False
    supports_photo: bool = False
    supports_before_after: bool = False
    supports_metrics: bool = False
    supports_case_reference: bool = False
    minimum_asset_count: int = Field(default=0, ge=0)
    maximum_asset_count: int = Field(default=8, ge=0)
    minimum_text_length: int = Field(default=0, ge=0)
    maximum_text_length: int = Field(default=2000, ge=0)
    density_range: tuple[float, float] = (0.2, 0.7)
    preview_image_path: str = ""
    page_width: float = Field(default=10.0, gt=0)
    page_height: float = Field(default=5.625, gt=0)
    extracted_fonts: list[str] = Field(default_factory=list)
    extracted_colors: list[str] = Field(default_factory=list)
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_notes: str = ""


class ArchitecturalTemplate(IdentifiedModel, VersionedModel, TimestampedModel):
    """Reusable architectural presentation template derived from a PPTX."""

    name: str = Field(min_length=1, max_length=200)
    source_pptx_path: str = ""
    project_id: UUID | None = None
    design_system_id: UUID | None = None
    reference_style_profile_id: UUID | None = None
    fonts: list[FontAsset] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    layouts: list[ArchitecturalTemplateLayout] = Field(default_factory=list)
    source_master_metadata: PowerPointMasterMetadata = Field(
        default_factory=PowerPointMasterMetadata
    )
    status: TemplateStatus = TemplateStatus.DRAFT
    workspace_dir: str = ""
    analysis_notes: list[str] = Field(default_factory=list)

    def layout_by_id(self, layout_id: str) -> ArchitecturalTemplateLayout | None:
        for layout in self.layouts:
            if layout.id == layout_id:
                return layout
        return None

    def layout_by_page_index(self, page_index: int) -> ArchitecturalTemplateLayout | None:
        for layout in self.layouts:
            if layout.page_index == page_index:
                return layout
        return None
