"""Reference PPT slide snapshots for template induction (not project content)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from archium.domain._base import DomainModel

# Asset origin for anything extracted from a reference PPTX.
REFERENCE_TEMPLATE_ASSET_ORIGIN = "reference_template"
REFERENCE_CASE_ASSET_ORIGIN = "reference_case"
PROJECT_ASSET_ORIGIN = "project_upload"


class ReferenceElementType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DRAWING = "drawing"
    CHART = "chart"
    TABLE = "table"
    SHAPE = "shape"
    GROUP = "group"
    PLACEHOLDER = "placeholder"
    DECORATION = "decoration"


class ReferenceAsset(DomainModel):
    """Image/media asset found on a reference slide — never project content."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    asset_origin: Literal[
        "reference_template",
        "reference_case",
        "project_upload",
    ] = REFERENCE_TEMPLATE_ASSET_ORIGIN
    # Relative path inside induction workspace (never machine absolute).
    # Example: assets/slide_003/image_002.png
    relative_path: str = ""
    width: float = Field(default=0.0, ge=0.0)
    height: float = Field(default=0.0, ge=0.0)
    content_hash: str = ""
    content_type: str = ""
    notes: str = ""

    @field_validator("relative_path")
    @classmethod
    def _forbid_absolute_asset_path(cls, value: str) -> str:
        text = (value or "").strip().replace("\\", "/")
        if not text:
            return ""
        if text.startswith(("/", "\\\\")) or (len(text) > 1 and text[1] == ":"):
            raise ValueError("relative_path must be workspace-relative, not machine absolute")
        return text


class ReferenceElement(DomainModel):
    """A shape / text / image / decoration on a reference slide."""

    id: str = Field(min_length=1)
    element_type: ReferenceElementType = ReferenceElementType.SHAPE
    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)
    z_index: int = Field(default=0, ge=0)
    text: str = ""
    font_name: str | None = None
    font_size_pt: float | None = None
    fill_color: str | None = None
    style_notes: list[str] = Field(default_factory=list)
    semantic_role: str = ""
    repeats_across_pages: bool = False
    likely_background_or_decoration: bool = False
    asset_id: str | None = None
    source_shape_name: str = ""
    # Picture accessibility description (cNvPr/@descr) — often empty on photos.
    alt_text: str = ""
    # Cross-page repeat fingerprint (type+geometry+style+content hashes).
    structural_signature: str = ""
    # Nested shapes when element_type == GROUP.
    children: list[ReferenceElement] = Field(default_factory=list)
    parse_ok: bool = True
    parse_warning: str = ""

    def iter_self_and_descendants(self) -> list[ReferenceElement]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.iter_self_and_descendants())
        return nodes


class ReferenceSlideSnapshot(DomainModel):
    """Parsed reference page — structure for induction, not project facts."""

    slide_index: int = Field(ge=0)
    slide_id: str = Field(min_length=1)

    # Relative path under induction workspace (e.g. slides/slide_001.png).
    image_path: str = ""
    width: float = Field(default=10.0, gt=0.0)
    height: float = Field(default=5.625, gt=0.0)

    master_name: str | None = None
    layout_name: str | None = None

    elements: list[ReferenceElement] = Field(default_factory=list)
    text_content: list[str] = Field(default_factory=list)
    image_assets: list[ReferenceAsset] = Field(default_factory=list)

    # Deterministic structural embedding (not a neural embedding requirement).
    visual_embedding: list[float] | None = None
    content_signature: str = ""

    notes: str = ""
    fonts: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)

    @field_validator("image_path")
    @classmethod
    def _forbid_absolute_image_path(cls, value: str) -> str:
        text = (value or "").strip().replace("\\", "/")
        if not text:
            return ""
        if text.startswith(("/", "\\\\")) or (len(text) > 1 and text[1] == ":"):
            raise ValueError("image_path must be workspace-relative, not machine absolute")
        return text

    def iter_elements(self) -> list[ReferenceElement]:
        nodes: list[ReferenceElement] = []
        for element in self.elements:
            nodes.extend(element.iter_self_and_descendants())
        return nodes

    @property
    def image_count(self) -> int:
        return sum(
            1
            for element in self.iter_elements()
            if element.element_type
            in {ReferenceElementType.IMAGE, ReferenceElementType.DRAWING}
        )

    @property
    def text_length(self) -> int:
        return sum(len(chunk) for chunk in self.text_content)

    @property
    def chart_count(self) -> int:
        return sum(
            1 for e in self.iter_elements() if e.element_type == ReferenceElementType.CHART
        )

    @property
    def table_count(self) -> int:
        return sum(
            1 for e in self.iter_elements() if e.element_type == ReferenceElementType.TABLE
        )


class ReferencePresentation(DomainModel):
    """Whole reference deck parse result."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    name: str = Field(min_length=1)
    source_filename: str = ""
    slide_count: int = Field(default=0, ge=0)
    page_width: float = Field(default=10.0, gt=0.0)
    page_height: float = Field(default=5.625, gt=0.0)
    fonts: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    slides: list[ReferenceSlideSnapshot] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Relative path to copied source.pptx inside workspace.
    source_pptx_relative: str = "source.pptx"
